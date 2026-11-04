"""Scientific sources behind every number this package reports.

VitalAge is an independent implementation. It is not affiliated with or
endorsed by the authors below.
"""

# (short label, full reference, DOI)
PHENOAGE = [
    ("Levine 2018",
     "Levine ME, Lu AT, Quach A, et al. An epigenetic biomarker of aging for "
     "lifespan and healthspan. Aging (Albany NY). 2018;10(4):573-591. "
     "Phenotypic Age (blood chemistry) is developed in this paper.",
     "10.18632/aging.101414"),
    ("Liu 2018",
     "Liu Z, Kuo PL, Horvath S, Crimmins E, Ferrucci L, Levine M. A new aging "
     "measure captures morbidity and mortality risk across diverse "
     "subpopulations from NHANES IV: a cohort study. PLoS Med. "
     "2018;15(12):e1002718. Validation of Phenotypic Age.",
     "10.1371/journal.pmed.1002718"),
    ("Kwon & Belsky 2021",
     "Kwon D, Belsky DW. A toolkit for quantification of biological age from "
     "blood chemistry and organ function test data: BioAge. GeroScience. "
     "2021;43(6):2795-2808. Source of the full-precision coefficients.",
     "10.1007/s11357-021-00480-5"),
]

FITNESS = [
    ("Zhang 2016",
     "Zhang D, Shen X, Qi X. Resting heart rate and all-cause and "
     "cardiovascular mortality in the general population: a meta-analysis. "
     "CMAJ. 2016;188(3):E53-63.",
     "10.1503/cmaj.150535"),
    ("Paluch 2022",
     "Paluch AE, Bajpai S, Bassett DR, et al. Daily steps and all-cause "
     "mortality: a meta-analysis of 15 international cohorts. Lancet Public "
     "Health. 2022;7(3):e219-e228.",
     "10.1016/S2468-2667(21)00302-9"),
    ("Kodama 2009",
     "Kodama S, Saito K, Tanaka S, et al. Cardiorespiratory fitness as a "
     "quantitative predictor of all-cause mortality and cardiovascular events "
     "in healthy men and women: a meta-analysis. JAMA. 2009;301(19):2024-2035.",
     "10.1001/jama.2009.681"),
    ("Kaminsky 2015",
     "Kaminsky LA, Arena R, Myers J. Reference standards for cardiorespiratory "
     "fitness measured with cardiopulmonary exercise testing: data from the "
     "FRIEND registry. Mayo Clin Proc. 2015;90(11):1515-1523.",
     "10.1016/j.mayocp.2015.07.026"),
    ("Cappuccio 2010",
     "Cappuccio FP, D'Elia L, Strazzullo P, Miller MA. Sleep duration and "
     "all-cause mortality: a systematic review and meta-analysis of "
     "prospective studies. Sleep. 2010;33(5):585-592.",
     "10.1093/sleep/33.5.585"),
]


def short_phenoage_credit():
    """One line for command-line output."""
    return ("Method: Phenotypic Age, Levine et al. 2018 (doi:10.18632/aging.101414); "
            "validated in Liu et al. 2018 (doi:10.1371/journal.pmed.1002718).")
