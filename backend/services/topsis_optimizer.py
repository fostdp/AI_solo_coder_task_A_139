import numpy as np
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.orm import ReinforcementPlan, ReinforcementMaterial, WallSegment
from ..models.schemas import TOPSISEvaluationRequest, TOPSISEvaluationResult


class TOPSISEvaluator:
    def __init__(self):
        self.default_criteria = [
            "penetration_depth",
            "durability_years",
            "cost_per_sqm",
            "construction_difficulty",
            "environmental_impact"
        ]
        self.default_weights = {
            "penetration_depth": 0.25,
            "durability_years": 0.25,
            "cost_per_sqm": 0.25,
            "construction_difficulty": 0.15,
            "environmental_impact": 0.10
        }
        self.default_benefit = ["penetration_depth", "durability_years"]
        self.default_cost = ["cost_per_sqm", "construction_difficulty", "environmental_impact"]

    def _normalize_matrix(self, matrix: np.ndarray) -> np.ndarray:
        norms = np.sqrt(np.sum(matrix**2, axis=0))
        norms = np.where(norms == 0, 1, norms)
        return matrix / norms

    def _apply_weights(self, normalized_matrix: np.ndarray, weights: np.ndarray) -> np.ndarray:
        return normalized_matrix * weights

    def _find_ideal_solutions(
        self,
        weighted_matrix: np.ndarray,
        benefit_indices: List[int],
        cost_indices: List[int]
    ) -> Tuple[np.ndarray, np.ndarray]:
        positive_ideal = np.copy(weighted_matrix[0])
        negative_ideal = np.copy(weighted_matrix[0])
        
        for j in range(weighted_matrix.shape[1]):
            if j in benefit_indices:
                positive_ideal[j] = np.max(weighted_matrix[:, j])
                negative_ideal[j] = np.min(weighted_matrix[:, j])
            else:
                positive_ideal[j] = np.min(weighted_matrix[:, j])
                negative_ideal[j] = np.max(weighted_matrix[:, j])
        
        return positive_ideal, negative_ideal

    def _calculate_distances(
        self,
        weighted_matrix: np.ndarray,
        positive_ideal: np.ndarray,
        negative_ideal: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        d_positive = np.sqrt(np.sum((weighted_matrix - positive_ideal)**2, axis=1))
        d_negative = np.sqrt(np.sum((weighted_matrix - negative_ideal)**2, axis=1))
        return d_positive, d_negative

    def _calculate_closeness(self, d_positive: np.ndarray, d_negative: np.ndarray) -> np.ndarray:
        total = d_positive + d_negative
        total = np.where(total == 0, 1, total)
        return d_negative / total

    def evaluate(
        self,
        alternatives: List[Dict[str, Any]],
        criteria: List[str],
        weights: Dict[str, float],
        benefit_criteria: List[str],
        cost_criteria: List[str]
    ) -> List[Dict[str, Any]]:
        if not alternatives:
            return []
        
        n_alternatives = len(alternatives)
        n_criteria = len(criteria)
        
        matrix = np.zeros((n_alternatives, n_criteria))
        criteria_to_idx = {c: i for i, c in enumerate(criteria)}
        
        for i, alt in enumerate(alternatives):
            for j, crit in enumerate(criteria):
                value = alt.get(crit, 0)
                if value is None:
                    value = 0
                matrix[i, j] = float(value)
        
        weight_array = np.array([weights.get(c, 1.0/n_criteria) for c in criteria])
        
        normalized = self._normalize_matrix(matrix)
        weighted = self._apply_weights(normalized, weight_array)
        
        benefit_indices = [criteria_to_idx[c] for c in benefit_criteria if c in criteria_to_idx]
        cost_indices = [criteria_to_idx[c] for c in cost_criteria if c in criteria_to_idx]
        
        positive_ideal, negative_ideal = self._find_ideal_solutions(
            weighted, benefit_indices, cost_indices
        )
        
        d_pos, d_neg = self._calculate_distances(weighted, positive_ideal, negative_ideal)
        closeness = self._calculate_closeness(d_pos, d_neg)
        
        ranked_indices = np.argsort(-closeness)
        
        results = []
        for rank, idx in enumerate(ranked_indices, 1):
            alt = alternatives[idx]
            criteria_scores = {}
            for j, crit in enumerate(criteria):
                criteria_scores[crit] = float(weighted[idx, j])
            
            results.append({
                "plan_id": alt.get("id"),
                "plan_name": alt.get("plan_name"),
                "material_type": alt.get("material_type"),
                "topsis_score": float(closeness[idx]),
                "topsis_rank": rank,
                "criteria_scores": criteria_scores,
                "d_positive": float(d_pos[idx]),
                "d_negative": float(d_neg[idx]),
                "is_selected": rank == 1
            })
        
        return results

    def calculate_penetration_depth(
        self,
        material_code: str,
        material_ratio: str,
        surface_hardness: float,
        soil_moisture: float,
        application_pressure: float = 0.5
    ) -> float:
        material_coefficients = {
            "TEOS-01": {"alpha": 0.75, "beta": 0.02, "gamma": 0.15},
            "TEOS-02": {"alpha": 0.68, "beta": 0.025, "gamma": 0.18},
            "GLU-01": {"alpha": 0.45, "beta": 0.015, "gamma": 0.10},
            "GLU-02": {"alpha": 0.52, "beta": 0.018, "gamma": 0.12},
            "COM-01": {"alpha": 0.60, "beta": 0.022, "gamma": 0.14}
        }
        
        coeff = material_coefficients.get(material_code, {"alpha": 0.5, "beta": 0.02, "gamma": 0.12})
        
        hardness_factor = np.exp(-coeff["beta"] * surface_hardness)
        moisture_factor = np.exp(-coeff["gamma"] * soil_moisture)
        pressure_factor = np.sqrt(application_pressure / 0.5)
        
        base_depth = 10.0
        penetration_depth = base_depth * coeff["alpha"] * hardness_factor * moisture_factor * pressure_factor
        
        return max(1.0, min(50.0, penetration_depth))

    def calculate_durability(
        self,
        material_code: str,
        penetration_depth: float,
        environment_factor: float = 1.0
    ) -> float:
        base_durability = {
            "TEOS-01": 25.0,
            "TEOS-02": 35.0,
            "GLU-01": 15.0,
            "GLU-02": 20.0,
            "COM-01": 30.0
        }
        
        base = base_durability.get(material_code, 20.0)
        penetration_factor = penetration_depth / 20.0
        durability = base * penetration_factor * environment_factor
        
        return max(5.0, durability)

    def calculate_environmental_impact(
        self,
        material_code: str,
        quantity: float = 1.0
    ) -> float:
        impact_factors = {
            "TEOS-01": 0.7,
            "TEOS-02": 0.85,
            "GLU-01": 0.15,
            "GLU-02": 0.20,
            "COM-01": 0.45
        }
        return impact_factors.get(material_code, 0.5) * quantity

    def calculate_cost(
        self,
        material_code: str,
        area: float,
        penetration_depth: float,
        material_cost_per_kg: float,
        application_cost_per_sqm: float = 15.0
    ) -> float:
        consumption_rate = 1.5
        material_quantity = area * (penetration_depth / 1000) * consumption_rate
        material_cost = material_quantity * material_cost_per_kg
        application_cost = area * application_cost_per_sqm
        total_cost = material_cost + application_cost
        return total_cost

    def generate_reinforcement_plans(
        self,
        segment_id: int,
        segment_area: float,
        avg_hardness: float,
        avg_moisture: float,
        erosion_severity: str = "medium"
    ) -> List[Dict[str, Any]]:
        materials = [
            {"code": "TEOS-01", "name": "硅酸乙酯", "ratio": "100%", "cost_kg": 45.0, "difficulty": 6},
            {"code": "TEOS-02", "name": "改性硅酸乙酯", "ratio": "TEOS+10%纳米SiO2", "cost_kg": 68.0, "difficulty": 7},
            {"code": "GLU-01", "name": "糯米灰浆", "ratio": "糯米:石灰=1:3", "cost_kg": 12.0, "difficulty": 3},
            {"code": "GLU-02", "name": "改性糯米灰浆", "ratio": "糯米:石灰:纳米CaO=1:3:0.1", "cost_kg": 18.0, "difficulty": 4},
            {"code": "COM-01", "name": "复合加固剂", "ratio": "TEOS:GLU=1:1", "cost_kg": 38.0, "difficulty": 8}
        ]
        
        severity_multiplier = {
            "low": 1.0,
            "medium": 1.2,
            "high": 1.5
        }
        mult = severity_multiplier.get(erosion_severity, 1.2)
        
        plans = []
        for mat in materials:
            penetration = self.calculate_penetration_depth(
                mat["code"], mat["ratio"], avg_hardness, avg_moisture
            ) * mult
            
            durability = self.calculate_durability(mat["code"], penetration)
            env_impact = self.calculate_environmental_impact(mat["code"], segment_area)
            cost_per_sqm = self.calculate_cost(mat["code"], 1.0, penetration, mat["cost_kg"])
            
            plans.append({
                "segment_id": segment_id,
                "plan_name": f"{mat['name']}加固方案",
                "material_type": mat["code"],
                "material_ratio": mat["ratio"],
                "penetration_depth": round(penetration, 2),
                "cost_per_sqm": round(cost_per_sqm, 2),
                "construction_difficulty": mat["difficulty"],
                "durability_years": round(durability, 1),
                "environmental_impact": round(env_impact, 3)
            })
        
        return plans

    async def evaluate_segment_plans(
        self,
        db: AsyncSession,
        request: TOPSISEvaluationRequest
    ) -> List[TOPSISEvaluationResult]:
        stmt = (
            select(ReinforcementPlan)
            .where(ReinforcementPlan.segment_id == request.segment_id)
            .order_by(ReinforcementPlan.created_at.desc())
        )
        result = await db.execute(stmt)
        plans = result.scalars().all()
        
        if not plans:
            segment = await db.get(WallSegment, request.segment_id)
            if not segment:
                raise ValueError(f"Segment {request.segment_id} not found")
            
            area = segment.length_m * segment.height_m
            avg_hardness = 2.5
            avg_moisture = 5.0
            
            generated_plans = self.generate_reinforcement_plans(
                request.segment_id, area, avg_hardness, avg_moisture, "medium"
            )
            
            for p in generated_plans:
                db_plan = ReinforcementPlan(**p)
                db.add(db_plan)
            await db.flush()
            
            result = await db.execute(stmt)
            plans = result.scalars().all()
        
        alternatives = []
        for plan in plans:
            alternatives.append({
                "id": plan.id,
                "plan_name": plan.plan_name,
                "material_type": plan.material_type,
                "penetration_depth": plan.penetration_depth or 0,
                "durability_years": plan.durability_years or 0,
                "cost_per_sqm": plan.cost_per_sqm or 0,
                "construction_difficulty": plan.construction_difficulty or 0,
                "environmental_impact": plan.environmental_impact or 0
            })
        
        results = self.evaluate(
            alternatives,
            self.default_criteria,
            request.weights,
            request.benefit_criteria,
            request.cost_criteria
        )
        
        for res in results:
            plan = await db.get(ReinforcementPlan, res["plan_id"])
            if plan:
                plan.topsis_score = res["topsis_score"]
                plan.topsis_rank = res["topsis_rank"]
                plan.is_selected = res["is_selected"]
        
        await db.commit()
        
        return [TOPSISEvaluationResult(**r) for r in results]


topsis_evaluator = TOPSISEvaluator()
