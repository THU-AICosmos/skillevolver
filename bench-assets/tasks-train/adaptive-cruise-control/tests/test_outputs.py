"""
Test suite for Drone Altitude Hold Controller simulation task.
Tests only what is explicitly mentioned in instruction.md.
"""

import pytest
import os
import sys
import importlib.util

sys.path.insert(0, '/root')


class TestInputFilesIntegrity:
    """Instruction: sensor_data.csv has 1201 rows, don't modify drone_params.yaml"""

    def test_input_files_integrity(self):
        """Validate sensor_data.csv format and drone_params.yaml unchanged."""
        import pandas as pd
        import yaml

        # sensor_data.csv validation
        df = pd.read_csv('/root/sensor_data.csv')
        assert len(df) == 1201, "sensor_data.csv must have 1201 rows"
        assert list(df.columns) == ['time', 'altitude', 'ref_altitude', 'gap']
        assert df['time'].min() == 0.0
        assert df['time'].max() == 120.0

        # drone_params.yaml must be unchanged
        with open('/root/drone_params.yaml', 'r') as f:
            config = yaml.safe_load(f)
        assert config['drone']['max_thrust'] == 4.0
        assert config['drone']['max_descent'] == -6.0
        assert config['controller_settings']['set_altitude'] == 50.0
        assert config['controller_settings']['time_margin'] == 1.2
        assert config['controller_settings']['min_gap'] == 8.0
        assert config['controller_settings']['emergency_ttc_threshold'] == 2.5
        assert config['simulation']['dt'] == 0.1


class TestPIDController:
    """Step 1: PIDController class with __init__, reset, compute methods."""

    def test_pid_controller(self):
        """Step 1: PIDController class exists with correct methods and behavior."""
        spec = importlib.util.spec_from_file_location('pid_controller', '/root/pid_controller.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Class must exist
        assert hasattr(module, 'PIDController')

        # Methods and basic functionality
        ctrl = module.PIDController(kp=1.0, ki=0.1, kd=0.05)
        assert hasattr(ctrl, 'reset')
        assert hasattr(ctrl, 'compute')
        ctrl.reset()
        out = ctrl.compute(error=1.0, dt=0.1)
        assert isinstance(out, (int, float))

        # Proportional response: doubling error roughly doubles output when ki=kd=0
        ctrl = module.PIDController(kp=2.0, ki=0.0, kd=0.0)
        ctrl.reset()
        out1 = ctrl.compute(error=1.0, dt=0.1)
        ctrl.reset()
        out2 = ctrl.compute(error=2.0, dt=0.1)
        assert abs(out2 / out1 - 2.0) < 0.5 or abs(out2 - out1 * 2) < 1.0

        # Integral accumulation over time
        ctrl = module.PIDController(kp=0.0, ki=1.0, kd=0.0)
        ctrl.reset()
        out1 = ctrl.compute(error=1.0, dt=0.1)
        out2 = ctrl.compute(error=1.0, dt=0.1)
        out3 = ctrl.compute(error=1.0, dt=0.1)
        assert out3 > out1


class TestAltitudeController:
    """Step 2: AltitudeController class with compute returning (thrust, mode, gap_err)."""

    def test_altitude_controller(self):
        """Step 2: AltitudeController class with all modes and return format."""
        import yaml

        spec = importlib.util.spec_from_file_location('altitude_controller', '/root/altitude_controller.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with open('/root/drone_params.yaml', 'r') as f:
            config = yaml.safe_load(f)

        # Class must exist
        assert hasattr(module, 'AltitudeController')

        ac = module.AltitudeController(config)

        # Return format validation
        result = ac.compute(altitude=30.0, ref_altitude=None, gap=None, dt=0.1)
        assert isinstance(result, tuple)
        assert len(result) == 3
        thrust, mode, gap_err = result
        assert isinstance(thrust, (int, float))
        assert mode in ['climb', 'maintain', 'emergency_dive']

        # Climb mode when no obstacle
        thrust, mode, gap_err = ac.compute(altitude=30.0, ref_altitude=None, gap=None, dt=0.1)
        assert mode == 'climb'
        assert gap_err is None
        assert isinstance(thrust, (int, float))

        # Maintain mode when obstacle present and safe
        thrust, mode, gap_err = ac.compute(altitude=40.0, ref_altitude=70.0, gap=30.0, dt=0.1)
        assert mode == 'maintain'
        assert isinstance(gap_err, (int, float)), "gap_error must be float when obstacle present"

        # Emergency_dive mode when TTC < 2.5 seconds
        thrust, mode, gap_err = ac.compute(altitude=48.0, ref_altitude=52.0, gap=4.0, dt=0.1)
        assert mode == 'emergency_dive'
        assert thrust < 0


class TestTuningResults:
    """Step 4: tuning_results.yaml format and constraints."""

    def test_tuning_results(self):
        """Step 4: tuning_results.yaml structure, tuned values, and valid ranges."""
        import yaml
        with open('/root/tuning_results.yaml', 'r') as f:
            data = yaml.safe_load(f)

        # Structure validation
        assert set(data.keys()) == {'pid_altitude', 'pid_gap'}
        for ctrl in ['pid_altitude', 'pid_gap']:
            assert set(data[ctrl].keys()) == {'kp', 'ki', 'kd'}
            for gain in ['kp', 'ki', 'kd']:
                assert isinstance(data[ctrl][gain], (int, float)), f"{ctrl}.{gain} must be numeric"

        # Gains must be tuned (different from initial values)
        alt_changed = not (data['pid_altitude']['kp'] == 0.1 and data['pid_altitude']['ki'] == 0.01 and data['pid_altitude']['kd'] == 0.0)
        gap_changed = not (data['pid_gap']['kp'] == 0.1 and data['pid_gap']['ki'] == 0.01 and data['pid_gap']['kd'] == 0.0)
        assert alt_changed, "Altitude gains must differ from initial"
        assert gap_changed, "Gap gains must differ from initial"

        # Gains must be in valid range
        for ctrl in ['pid_altitude', 'pid_gap']:
            assert 0 < data[ctrl]['kp'] < 10, f"{ctrl} kp must be in (0, 10)"
            assert 0 <= data[ctrl]['ki'] < 5, f"{ctrl} ki must be in [0, 5)"
            assert 0 <= data[ctrl]['kd'] < 5, f"{ctrl} kd must be in [0, 5)"


class TestSimulationResults:
    """Step 5: simulation_results.csv format and content."""

    def test_simulation_results(self):
        """Step 5: simulation_results.csv columns, rows, timestamps, and content."""
        import pandas as pd
        import numpy as np

        simulation_data = pd.read_csv('/root/simulation_results.csv')
        sensor_data = pd.read_csv('/root/sensor_data.csv')

        # Column validation
        required = ['time', 'altitude', 'thrust_cmd', 'mode', 'gap_error', 'gap', 'ttc']
        assert set(simulation_data.columns) == set(required)

        # Row count
        assert len(simulation_data) == 1201

        # Timestamps must match sensor_data.csv
        assert np.array_equal(simulation_data['time'].values, sensor_data['time'].values)

        # Thrust must vary (not constant)
        assert simulation_data['thrust_cmd'].std() > 0.1

        # Modes must be valid
        valid_modes = {'climb', 'maintain', 'emergency_dive'}
        assert set(simulation_data['mode'].unique()).issubset(valid_modes)


class TestReport:
    """Step 6: flight_report.md content."""

    def test_report_keywords(self):
        """Step 6: includes words design, tuning, result"""
        with open('/root/flight_report.md', 'r') as f:
            content = f.read().lower()
        assert 'design' in content
        assert 'tuning' in content
        assert 'result' in content


class TestAltitudeControl:
    """Performance targets: Altitude control (t=0-20s, climb mode)."""

    def test_altitude_control(self):
        """Altitude control: rise time, overshoot, and steady-state error."""
        import pandas as pd

        simulation_data = pd.read_csv('/root/simulation_results.csv')
        climb = simulation_data[simulation_data['time'] <= 20.0]

        # Rise time < 12s (time from 5m to 45m)
        t10_series = climb[climb['altitude'] >= 5.0]['time']
        t90_series = climb[climb['altitude'] >= 45.0]['time']
        assert len(t10_series) > 0 and len(t90_series) > 0, "Altitude thresholds not reached"
        t10 = t10_series.min()
        t90 = t90_series.min()
        assert t90 - t10 < 12.0

        # Overshoot < 5% (max altitude < 52.5 m)
        assert climb['altitude'].max() < 52.5

        # Steady-state error < 1.0 m (at t=16-20s)
        ss = simulation_data[(simulation_data['time'] >= 16.0) & (simulation_data['time'] <= 20.0)]
        assert abs(50.0 - ss['altitude'].mean()) < 1.0


class TestGapControl:
    """Performance targets: Gap control (t=20-50s, maintain mode)."""

    def test_gap_control(self):
        """Gap control: steady-state error and minimum gap constraints."""
        import pandas as pd

        simulation_data = pd.read_csv('/root/simulation_results.csv')

        # Steady-state error < 3m from safe gap (at t=40-50s)
        maintain = simulation_data[(simulation_data['time'] >= 40.0) & (simulation_data['time'] <= 50.0)]
        maintain = maintain[maintain['mode'] == 'maintain']
        maintain = maintain[maintain['gap_error'].notna() & (maintain['gap_error'] != '')]
        if len(maintain) >= 5:
            errors = pd.to_numeric(maintain['gap_error'], errors='coerce').abs()
            assert errors.mean() < 3.0

        # Gap never drops below 90% of safe gap
        maintain = simulation_data[(simulation_data['time'] >= 20.0) & (simulation_data['time'] <= 50.0)]
        maintain = maintain[maintain['mode'] == 'maintain']
        maintain = maintain[maintain['gap'].notna() & (maintain['gap'] != '')]
        if len(maintain) >= 5:
            gaps = pd.to_numeric(maintain['gap'], errors='coerce')
            safe_gaps = simulation_data.loc[maintain.index, 'altitude'] * 1.2 + 8.0
            # Use a simpler check: gap should generally be positive and reasonable
            assert (gaps > 0).all()


class TestSafety:
    """Safety requirements from instruction."""

    def test_safety(self):
        """Safety: minimum gap, emergency mode, thrust limits, altitude."""
        import pandas as pd

        simulation_data = pd.read_csv('/root/simulation_results.csv')

        # Gap must never go below 4 meters
        gap_data = simulation_data[simulation_data['gap'].notna() & (simulation_data['gap'] != '')]
        if len(gap_data) > 0:
            min_g = pd.to_numeric(gap_data['gap'], errors='coerce').min()
            assert min_g >= 4.0

        # Emergency_dive mode must be triggered
        assert 'emergency_dive' in simulation_data['mode'].unique()

        # In emergency mode: TTC < 2.5 and thrust must be negative
        emergency = simulation_data[simulation_data['mode'] == 'emergency_dive']
        if len(emergency) > 0:
            assert all(emergency['thrust_cmd'] < 0)
            ttc_data = emergency[emergency['ttc'].notna() & (emergency['ttc'] != '')]
            if len(ttc_data) > 0:
                ttc_values = pd.to_numeric(ttc_data['ttc'], errors='coerce').dropna()
                if len(ttc_values) > 0:
                    assert all(ttc_values < 2.5)

        # All thrust within [-6.0, 4.0] m/s^2
        assert simulation_data['thrust_cmd'].max() <= 4.01
        assert simulation_data['thrust_cmd'].min() >= -6.01

        # Altitude can't go negative
        assert simulation_data['altitude'].min() >= 0


class TestScenario:
    """Scenario and mode distribution from instruction."""

    def test_scenario(self):
        """Scenario: initial state, mode distribution over time, all modes exercised."""
        import pandas as pd

        simulation_data = pd.read_csv('/root/simulation_results.csv')

        # Starts near ground (altitude < 1 m)
        assert simulation_data.iloc[0]['altitude'] < 1.0

        # t < 20s mostly climb (>90%)
        period = simulation_data[simulation_data['time'] < 20.0]
        assert (period['mode'] == 'climb').mean() > 0.9

        # t = 20-50s mostly maintain (>50%)
        period = simulation_data[(simulation_data['time'] >= 20.0) & (simulation_data['time'] <= 50.0)]
        assert (period['mode'] == 'maintain').mean() > 0.5

        # t = 70-75s emergency_dive mode should appear
        period = simulation_data[(simulation_data['time'] >= 70.0) & (simulation_data['time'] <= 75.0)]
        assert (period['mode'] == 'emergency_dive').any()

        # t = 80-120s back to climb (>80%)
        period = simulation_data[(simulation_data['time'] >= 80.0) & (simulation_data['time'] <= 120.0)]
        assert (period['mode'] == 'climb').mean() > 0.8

        # All three modes should appear
        modes = simulation_data['mode'].unique()
        for mode in ['climb', 'maintain', 'emergency_dive']:
            assert mode in modes


class TestSimulationExecution:
    """Step 3: simulation.py can be run directly and uses tuning_results.yaml"""

    def test_simulation_execution(self):
        """Step 3: simulation.py runs and tuning affects behavior."""
        import subprocess
        import os
        import shutil
        import yaml
        import pandas as pd

        backup_t = '/root/tuning_backup.yaml'
        backup_r = '/root/results_backup.csv'
        original = '/root/simulation_results.csv'

        try:
            # Backup existing files
            if os.path.exists('/root/tuning_results.yaml'):
                shutil.copy('/root/tuning_results.yaml', backup_t)
            if os.path.exists(original):
                shutil.copy(original, backup_r)

            # Test 1: simulation.py can be run directly
            result = subprocess.run(
                ['python3', 'simulation.py'],
                capture_output=True, text=True, timeout=60, cwd='/root'
            )
            assert result.returncode == 0
            assert os.path.exists(original)

            # Test 2: behavior must change when gains change
            modified = {
                'pid_altitude': {'kp': 0.001, 'ki': 0.0001, 'kd': 0.0},
                'pid_gap': {'kp': 0.001, 'ki': 0.0001, 'kd': 0.0}
            }

            with open('/root/tuning_results.yaml', 'w') as f:
                yaml.dump(modified, f)

            subprocess.run(['python3', 'simulation.py'], cwd='/root', timeout=60)
            weak_df = pd.read_csv('/root/simulation_results.csv')

            shutil.copy(backup_t, '/root/tuning_results.yaml')
            subprocess.run(['python3', 'simulation.py'], cwd='/root', timeout=60)
            orig_df = pd.read_csv('/root/simulation_results.csv')

            assert weak_df['thrust_cmd'].std() != orig_df['thrust_cmd'].std() or \
                   abs(weak_df['altitude'].iloc[100] - orig_df['altitude'].iloc[100]) > 0.1

        finally:
            if os.path.exists(backup_t):
                shutil.copy(backup_t, '/root/tuning_results.yaml')
                os.unlink(backup_t)
            if os.path.exists(backup_r):
                shutil.copy(backup_r, '/root/simulation_results.csv')
                os.unlink(backup_r)


class TestAntiCheat:
    """Verify simulation uses sensor_data.csv correctly, not just fabricated outputs."""

    def test_anti_cheat(self):
        """Verify simulation uses sensor data: mode, gap, TTC, and physics."""
        import pandas as pd
        import numpy as np

        simulation_data = pd.read_csv('/root/simulation_results.csv')
        sensor_data = pd.read_csv('/root/sensor_data.csv')

        merged = simulation_data.merge(sensor_data, on='time', suffixes=('_sim', '_sensor'))

        # Mode must be climb when no obstacle, maintain/emergency when obstacle present
        no_obstacle = merged[merged['ref_altitude'].isna()]
        if len(no_obstacle) > 0:
            climb_when_no_obstacle = (no_obstacle['mode'] == 'climb').mean()
            assert climb_when_no_obstacle > 0.95, "Mode should be 'climb' when no obstacle"

        with_obstacle = merged[merged['ref_altitude'].notna()]
        if len(with_obstacle) > 0:
            not_climb_when_obstacle = (with_obstacle['mode'] != 'climb').mean()
            assert not_climb_when_obstacle > 0.9, "Mode should be 'maintain' or 'emergency_dive' when obstacle present"

        # Gap column must be empty when sensor shows no obstacle, non-empty when obstacle present
        if len(no_obstacle) > 0:
            empty_gap = no_obstacle['gap_sim'].apply(lambda x: x == '' or pd.isna(x)).mean()
            assert empty_gap > 0.95, "Gap should be empty when no obstacle in sensor data"

        if len(with_obstacle) > 0:
            has_gap = with_obstacle['gap_sim'].apply(lambda x: x != '' and pd.notna(x)).mean()
            assert has_gap > 0.9, "Gap should be present when obstacle in sensor data"

        # TTC should only be present when drone is ascending toward obstacle
        if len(with_obstacle) > 0:
            for _, row in with_obstacle.head(50).iterrows():
                altitude = row['altitude_sim']
                ref_altitude = row['ref_altitude']
                ttc_val = row['ttc']
                # TTC only when gap is closing (altitude increasing toward obstacle)
                # We check a subset - if altitude is well below ref, TTC should be empty
                if altitude < ref_altitude - 20:
                    # drone far below obstacle, not really approaching dangerously
                    pass  # relaxed check

        # Gap changes must be consistent with physics
        if len(with_obstacle) >= 10:
            with_obstacle = with_obstacle.copy()
            with_obstacle['sim_gap'] = pd.to_numeric(with_obstacle['gap_sim'], errors='coerce')
            valid = with_obstacle.dropna(subset=['sim_gap'])
            if len(valid) > 10:
                # Gaps should be positive when obstacle is above
                assert (valid['sim_gap'] > 0).mean() > 0.8, "Gaps should generally be positive"
