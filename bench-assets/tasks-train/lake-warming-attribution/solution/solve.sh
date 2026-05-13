#!/bin/bash
set -e

python3 << 'PYTHON'
import pandas as pd
import numpy as np
from scipy import stats
import pymannkendall as mk
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from factor_analyzer import FactorAnalyzer
import os


class AcidificationAnalyzer:
    """Analyze ocean acidification trends and attribution."""

    def __init__(self, data_dir='/root/data', out_dir='/root/output'):
        self.data_dir = data_dir
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)

    def load_datasets(self):
        self.ph_data = pd.read_csv(f'{self.data_dir}/ocean_ph.csv')
        self.atmos = pd.read_csv(f'{self.data_dir}/atmospheric.csv')
        self.chem = pd.read_csv(f'{self.data_dir}/ocean_chemistry.csv')
        self.circ = pd.read_csv(f'{self.data_dir}/circulation.csv')
        self.coastal = pd.read_csv(f'{self.data_dir}/coastal_activity.csv')

    def run_trend_test(self):
        ph_series = self.ph_data['OceanPH'].values
        mk_out = mk.original_test(ph_series)
        sen_slope = round(mk_out.slope, 3)
        pval = round(mk_out.p, 4)
        pd.DataFrame({'slope': [sen_slope], 'p_value': [pval]}).to_csv(
            f'{self.out_dir}/ph_trend.csv', index=False)
        print(f"Trend test: slope={sen_slope}, p={pval}")

    def _compute_r_squared(self, features, target):
        reg = LinearRegression().fit(features, target)
        predicted = reg.predict(features)
        residual_ss = np.sum((target - predicted) ** 2)
        total_ss = np.sum((target - target.mean()) ** 2)
        return 1.0 - residual_ss / total_ss

    def run_attribution(self):
        merged = self.ph_data.copy()
        for frame in [self.atmos, self.chem, self.circ, self.coastal]:
            merged = merged.merge(frame, on='Year')

        merged['TotalCO2'] = merged['CO2_ppm'] + merged['DissolvedCO2'] / 10.0

        predictor_names = [
            'TotalCO2', 'AirTemperature',
            'ShippingTraffic', 'IndustrialDischarge',
            'CurrentSpeed', 'Upwelling',
            'SolarRadiation', 'CO2_ppm',
        ]

        feat_matrix = merged[predictor_names].values
        response = merged['OceanPH'].values

        normed = StandardScaler().fit_transform(feat_matrix)

        analyzer = FactorAnalyzer(n_factors=4, rotation='varimax')
        analyzer.fit(normed)
        factor_scores = analyzer.transform(normed)
        weight_matrix = analyzer.loadings_

        overall_r2 = self._compute_r_squared(factor_scores, response)

        # Map factors to categories based on loadings
        # Chemical: TotalCO2 (index 0), Coastal: ShippingTraffic (2), Circulation: Upwelling (5), Atmospheric: SolarRadiation (6)
        category_map = {
            'Chemical': int(np.argmax(np.abs(weight_matrix[0]))),
            'Coastal': int(np.argmax(np.abs(weight_matrix[2]))),
            'Circulation': int(np.argmax(np.abs(weight_matrix[5]))),
            'Atmospheric': int(np.argmax(np.abs(weight_matrix[6]))),
        }

        category_contributions = {}
        for cat_name, fac_idx in category_map.items():
            remaining = [j for j in range(4) if j != fac_idx]
            partial_r2 = self._compute_r_squared(factor_scores[:, remaining], response)
            category_contributions[cat_name] = (overall_r2 - partial_r2) * 100.0

        top_cat = max(category_contributions, key=category_contributions.get)
        top_pct = round(category_contributions[top_cat])

        pd.DataFrame({'category': [top_cat], 'pct_contribution': [top_pct]}).to_csv(
            f'{self.out_dir}/key_driver.csv', index=False)
        print(f"Key driver: {top_cat} ({top_pct}%)")
        for c, v in category_contributions.items():
            print(f"  {c}: {v:.1f}%")


analyzer = AcidificationAnalyzer()
analyzer.load_datasets()
analyzer.run_trend_test()
analyzer.run_attribution()
PYTHON
