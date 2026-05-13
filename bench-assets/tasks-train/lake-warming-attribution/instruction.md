My data is in `/root/data/`, which includes:
1. `ocean_ph.csv`: Coastal ocean surface pH measurements
2. `atmospheric.csv`: Atmospheric variables
3. `ocean_chemistry.csv`: Ocean chemistry data
4. `circulation.csv`: Ocean circulation data
5. `coastal_activity.csv`: Human coastal activity data

First, I want to do a trend analysis to determine whether there is a long-term acidification trend (pH decline) in the ocean. You should output the 'ph_trend.csv' in '/root/output/'. The file should have two columns: one is "slope," and the other is "p_value."

Second, I want to know the most important driving factor behind the ocean acidification. To simplify, all driving factors listed in our data can be classified into Chemical, Circulation, Atmospheric, and Coastal. You should combine CO2_ppm and DissolvedCO2/10 into a single TotalCO2 metric first. Then, you can just tell me which category is the most important category, and what percentage of this category contributes to the pH change. You should output the 'key_driver.csv' in '/root/output/'. The file should have two columns: one is "category," and the other is "pct_contribution." You only need to output the most important category.
