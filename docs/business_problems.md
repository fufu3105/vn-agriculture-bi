# Business problems

Rice procurement and processing enterprises need to understand where rice is produced, how production changes over time, and what to monitor when planning supply. The BI system uses annual provincial statistics from Vietnam's National Statistics Office (NSO), with historical weather data for BP4. Each business problem has its own dashboard.

The project uses consistent province identifiers and historical boundaries, standardizes units and year keys, and records publication status where the source provides it. Regional figures are built from province records using the project's seven-region mapping. National and regional totals published in the source are excluded from these sums.

## BP1 · Assessing Rice Sourcing Regions (Descriptive Analytics)

**Where is rice production concentrated, and how have the scale and stability of production changed?** Compare rice production, sown area, yield, and historical trends across provinces and regions. Use the results to identify places for further sourcing assessment. The final assessment of regional priorities draws on all four dashboards.

## BP2 · Explaining Production Changes (Diagnostic Analytics)

**How much of the reported production change between two years is associated with changes in sown area and yield?** Calculate the area and yield contributions for each province and sum them by region and nationally. Show the reconciliation gap between the reported change and the change implied by area × yield. Compare which provinces and regions contributed most to the increase or decrease and use the results to guide follow-up. The contributions come from an arithmetic decomposition. Establishing causes requires separate evidence. [BP2 calculation and dashboard](bp/bp2.md)

## BP3 · Forecasting Rice Production (Predictive Analytics)

**What is the outlook for provincial rice production next year, and how accurate has the forecasting approach been?** Produce one-year-ahead estimates using information available at the forecast date. Compare against a baseline on historical periods in chronological order, with each test year kept out of its training data. Use the forecast and historical errors to assess the outlook and prepare sourcing scenarios.

## BP4 · Examining Weather-Related Yield Variation (Diagnostic Analytics)

**Where and when do temperature and rainfall vary alongside rice yield?** Join historical weather and NSO yield data at the province–year level. Compare statistical associations across places and years to identify areas for closer monitoring. Establishing causal effects requires additional evidence about growing conditions and other factors.

Reported provincial production indicates potential supply. Procurement volumes depend on available suppliers, prices, quality requirements and logistics.
