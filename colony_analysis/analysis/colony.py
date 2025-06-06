# ============================================================================
# 9. colony_analysis/analysis/colony.py - 菌落分析器
# ============================================================================

import logging
from typing import Dict, List, Optional

import numpy as np
from tqdm import tqdm

from ..core.sam_model import SAMModel
from .features import FeatureExtractor
from .scoring import ScoringSystem


class ColonyAnalyzer:
    """菌落分析器 - 提取特征并进行评分分类"""

    def __init__(
        self,
        sam_model: Optional[SAMModel] = None,
        config=None,
        debug: bool = False,
        orientation: str = "front",
    ):
        """初始化菌落分析器"""
        self.sam_model = sam_model
        self.config = config
        self.debug = debug
        self.orientation = orientation.lower() if orientation else "front"
        self.feature_extractors = []
        self.scoring_system = ScoringSystem()
        self._init_feature_extractors()

        logging.info("菌落分析器已初始化")

    def _init_feature_extractors(self):
        """初始化特征提取器"""
        if self.orientation == "back":
            # 背面图像主要分析色素产物
            self.feature_extractors = [
                FeatureExtractor(extractor_type="basic", debug=self.debug),
                FeatureExtractor(extractor_type="metabolite", debug=self.debug),
            ]
        else:
            # 正面图像关注形态和气生菌丝
            self.feature_extractors = [
                FeatureExtractor(extractor_type="basic", debug=self.debug),
                FeatureExtractor(extractor_type="aerial", debug=self.debug),
            ]

    def analyze(self, colonies: List[Dict], advanced: bool = False) -> List[Dict]:
        """分析菌落列表"""
        if not colonies:
            logging.warning("没有菌落需要分析")
            return []

        analyzed_colonies = []

        for i, colony in enumerate(tqdm(colonies, desc="分析菌落", ncols=80)):
            try:
                analyzed_colony = self.analyze_colony(colony, advanced)
                analyzed_colonies.append(analyzed_colony)
            except Exception as e:
                logging.error(f"分析菌落 {i} 时出错: {e}")
                analyzed_colonies.append(colony)

        logging.info(f"菌落分析完成，共 {len(analyzed_colonies)} 个")
        return analyzed_colonies

    def analyze_colony(self, colony: Dict, advanced: bool = False) -> Dict:
        """分析单个菌落"""
        # 确保有基本数据结构
        if "features" not in colony:
            colony["features"] = {}
        if "scores" not in colony:
            colony["scores"] = {}
        if "phenotype" not in colony:
            colony["phenotype"] = {}

        # 检查必要的字段
        if "img" not in colony or "mask" not in colony:
            logging.warning(f"菌落 {colony.get('id', 'unknown')} 缺少图像或掩码数据")
            return colony

        # 提取特征
        for extractor in self.feature_extractors:
            features = extractor.extract(colony["img"], colony["mask"])
            colony["features"].update(features)

        # 计算评分
        scores = self.scoring_system.calculate_scores(colony["features"])
        colony["scores"].update(scores)

        # 分类表型
        phenotype = self.scoring_system.classify_phenotype(colony["features"])
        colony["phenotype"].update(phenotype)

        # 高级分析
        if advanced and self.sam_model is not None:
            self._perform_advanced_analysis(colony)

        # 使用质量分数进行加权
        quality = colony.get("quality_score", 0.5)
        if quality < 0.3:
            logging.warning(f"低质量菌落: {colony['id']}")

        # 处理跨界情况
        if colony.get("cross_boundary", False):
            colony["phenotype"]["special_case"] = "cross_boundary"
            # 将列表转换为逗号分隔的字符串
            affected_wells = colony.get("overlapping_wells", [])
            colony["phenotype"]["affected_wells"] = (
                ", ".join(affected_wells) if affected_wells else "none"
            )
        return colony

    def _perform_advanced_analysis(self, colony: Dict):
        """执行高级分析"""
        try:
            # 检测扩散区域
            diffusion_mask = self.sam_model.find_diffusion_zone(
                colony["img"], colony["mask"]
            )

            if "advanced_masks" not in colony:
                colony["advanced_masks"] = {}

            colony["advanced_masks"]["diffusion"] = diffusion_mask

            # 计算扩散特征
            diffusion_area = np.sum(diffusion_mask)
            colony_area = np.sum(colony["mask"])
            diffusion_ratio = diffusion_area / colony_area if colony_area > 0 else 0

            colony["features"]["metabolite_diffusion_ratio"] = float(diffusion_ratio)

        except Exception as e:
            logging.error(f"高级分析失败: {e}")
