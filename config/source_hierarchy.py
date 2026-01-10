"""Source Hierarchy Configuration for Representative Article Selection"""

# =============================================================================
# Foreign Sources (Tier 1-99): Lower is better
# =============================================================================

# Tier 1: Bloomberg
SOURCE_TIER_FOREIGN_1 = ["Bloomberg"]

# Tier 2: Financial Times
SOURCE_TIER_FOREIGN_2 = ["FT", "Financial Times"]

# Tier 3: WSJ
SOURCE_TIER_FOREIGN_3 = ["WSJ", "Wall Street Journal"]

# Tier 4: Reuters
SOURCE_TIER_FOREIGN_4 = ["Reuters"]

# Tier 5: Big Tech
SOURCE_TIER_FOREIGN_5 = ["Big Tech", "TechCrunch", "TheVerge", "CNBC"]

# Tier 6: US Real Estate
SOURCE_TIER_FOREIGN_6 = ["US Real Estate"]

# Tier 99: Other Foreign Sources
# CNN, BBC, etc.

# =============================================================================
# Domestic Sources (Tier 101-199): Lower is better
# =============================================================================

# Tier 101: Korean Economy
SOURCE_TIER_DOMESTIC_101 = ["Korean Economy", "한국경제", "Hankyung"]

# Tier 102: Infomax
SOURCE_TIER_DOMESTIC_102 = ["Infomax"]

# Tier 103: Naver Finance
SOURCE_TIER_DOMESTIC_103 = ["Naver Finance"]

# Tier 199: Other Domestic Sources
# 매일경제, 연합뉴스, 조선일보 등


def get_source_tier(source: str) -> int:
    """
    소스의 Tier를 반환합니다.
    
    Priority order:
    - Foreign: Bloomberg(1) > FT(2) > WSJ(3) > Reuters(4) > Big Tech(5) > US Real Estate(6) > Others(99)
    - Domestic: Korean Economy(101) > Infomax(102) > Naver Finance(103) > Others(199)
    
    Args:
        source: 소스명 (정규화 전/후 모두 가능)
        
    Returns:
        Tier 번호 (1-99: Foreign, 101-199: Domestic)
    """
    if not source:
        return 999  # Unknown
    
    source_upper = source.upper()
    source_lower = source.lower()
    
    # Foreign Sources
    for tier1_source in SOURCE_TIER_FOREIGN_1:
        if tier1_source.lower() in source_lower or tier1_source.upper() in source_upper:
            return 1
    
    for tier2_source in SOURCE_TIER_FOREIGN_2:
        if tier2_source.lower() in source_lower or tier2_source.upper() in source_upper:
            return 2
    
    for tier3_source in SOURCE_TIER_FOREIGN_3:
        if tier3_source.lower() in source_lower or tier3_source.upper() in source_upper:
            return 3
    
    for tier4_source in SOURCE_TIER_FOREIGN_4:
        if tier4_source.lower() in source_lower or tier4_source.upper() in source_upper:
            return 4
    
    for tier5_source in SOURCE_TIER_FOREIGN_5:
        if tier5_source.lower() in source_lower or tier5_source.upper() in source_upper:
            return 5
    
    for tier6_source in SOURCE_TIER_FOREIGN_6:
        if tier6_source.lower() in source_lower or tier6_source.upper() in source_upper:
            return 6
    
    # Domestic Sources
    for tier101_source in SOURCE_TIER_DOMESTIC_101:
        if tier101_source.lower() in source_lower or tier101_source.upper() in source_upper:
            return 101
    
    for tier102_source in SOURCE_TIER_DOMESTIC_102:
        if tier102_source.lower() in source_lower or tier102_source.upper() in source_upper:
            return 102
    
    for tier103_source in SOURCE_TIER_DOMESTIC_103:
        if tier103_source.lower() in source_lower or tier103_source.upper() in source_upper:
            return 103
    
    # Check if domestic or foreign based on language
    # Korean characters indicate domestic
    if any('\uac00' <= c <= '\ud7a3' for c in source):
        return 199  # Other domestic
    else:
        return 99  # Other foreign


def compare_sources(source1: str, source2: str) -> int:
    """
    두 소스를 비교하여 우선순위를 반환합니다.
    
    Args:
        source1: 첫 번째 소스
        source2: 두 번째 소스
        
    Returns:
        -1: source1이 우선순위 높음 (낮은 tier)
        0: 동일한 Tier
        1: source2가 우선순위 높음 (낮은 tier)
    """
    tier1 = get_source_tier(source1)
    tier2 = get_source_tier(source2)
    
    if tier1 < tier2:
        return -1  # source1이 더 높은 우선순위
    elif tier1 > tier2:
        return 1   # source2가 더 높은 우선순위
    else:
        return 0   # 동일한 Tier



