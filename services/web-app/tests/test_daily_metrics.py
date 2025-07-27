import pytest
from datetime import date, timedelta
from app.models.models import User, HealthProfile, DailyMetric
from app.extensions import db

def create_user(account, password, is_staff=False, is_admin=False, first_name="Test", last_name="User"):
    """Helper function to create a user."""
    user = User(
        account=account,
        is_staff=is_staff,
        is_admin=is_admin,
        first_name=first_name,
        last_name=last_name,
        email=f"{account}@test.com"
    )
    user.set_password(password)
    return user

def create_patient(session, account, password):
    """Helper function to create a patient."""
    patient = create_user(account, password, is_staff=False)
    session.add(patient)
    session.commit()
    health_profile = HealthProfile(user_id=patient.id)
    session.add(health_profile)
    session.commit()
    return patient

@pytest.fixture(scope='function')
def setup_metrics(session):
    """Fixture to set up a patient and some daily metrics."""
    patient1 = create_patient(session, 'patient_metrics', 'password')

    # Create another patient for permission tests
    patient2 = create_patient(session, 'patient_metrics2', 'password')

    # Create some historical data for patient1
    for i in range(5):
        log_date = date.today() - timedelta(days=i + 2) # Avoid today and yesterday
        metric = DailyMetric(
            user_id=patient1.id,
            water_cc=2000 + i,
            medication=True,
            exercise_min=30 + i,
            cigarettes=i,
            created_at=log_date
        )
        session.add(metric)

    session.commit()

    return {
        "patient1": patient1,
        "patient2": patient2
    }

def test_create_daily_metric_success(client, setup_metrics):
    """T-4.2: Test successfully creating a new daily metric."""
    patient = setup_metrics["patient1"]

    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_metrics', 'password': 'password'})
    access_token = login_res.json['data']['token']

    data = {
        "water_cc": 2500,
        "medication": True,
        "exercise_min": 45,
        "cigarettes": 0
    }

    res = client.post(f'/api/v1/patients/{patient.id}/daily_metrics', json=data, headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 201
    assert res.json['data']['water_cc'] == 2500

def test_create_daily_metric_conflict(client, setup_metrics):
    """T-4.2: Test creating a daily metric for a date that already has one."""
    patient = setup_metrics["patient1"]

    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_metrics', 'password': 'password'})
    access_token = login_res.json['data']['token']

    data = {
        "water_cc": 2500,
        "medication": True,
        "exercise_min": 45,
        "cigarettes": 0
    }

    # Create the first metric for today
    res = client.post(f'/api/v1/patients/{patient.id}/daily_metrics', json=data, headers={'Authorization': f'Bearer {access_token}'})
    assert res.status_code == 201

    # Try to create another one on the same day
    res = client.post(f'/api/v1/patients/{patient.id}/daily_metrics', json=data, headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 409

def test_create_daily_metric_forbidden(client, setup_metrics):
    """T-4.2: Test that a patient cannot create a metric for another patient."""
    patient1 = setup_metrics["patient1"]
    patient2 = setup_metrics["patient2"]

    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_metrics2', 'password': 'password'})
    access_token = login_res.json['data']['token']

    data = {"water_cc": 1000}

    # patient2 tries to create a metric for patient1
    res = client.post(f'/api/v1/patients/{patient1.id}/daily_metrics', json=data, headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 403

def test_update_daily_metric_success(client, setup_metrics):
    """T-4.3: Test successfully updating an existing daily metric."""
    patient = setup_metrics["patient1"]
    log_date = date.today() - timedelta(days=2)

    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_metrics', 'password': 'password'})
    access_token = login_res.json['data']['token']

    data = {"water_cc": 9999}

    res = client.put(f'/api/v1/patients/{patient.id}/daily_metrics/{log_date.strftime("%Y-%m-%d")}', json=data, headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 200
    assert res.json['data']['water_cc'] == 9999

def test_get_daily_metrics_success(client, setup_metrics):
    """T-4.4: Test successfully getting a list of daily metrics."""
    patient = setup_metrics["patient1"]

    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_metrics', 'password': 'password'})
    access_token = login_res.json['data']['token']

    res = client.get(f'/api/v1/patients/{patient.id}/daily_metrics', headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 200
    assert len(res.json['data']) == 5

def test_get_daily_metrics_date_range(client, setup_metrics):
    """T-4.4: Test getting daily metrics within a specific date range."""
    patient = setup_metrics["patient1"]

    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_metrics', 'password': 'password'})
    access_token = login_res.json['data']['token']

    start_date = (date.today() - timedelta(days=4)).strftime('%Y-%m-%d')
    end_date = (date.today() - timedelta(days=2)).strftime('%Y-%m-%d')

    res = client.get(f'/api/v1/patients/{patient.id}/daily_metrics?start_date={start_date}&end_date={end_date}', headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 200
    assert len(res.json['data']) == 3

def test_update_daily_metric_not_found(client, setup_metrics):
    """T-4.3: Test updating a metric for a non-existent date."""
    patient = setup_metrics["patient1"]
    non_existent_date = "1999-01-01"

    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_metrics', 'password': 'password'})
    access_token = login_res.json['data']['token']

    data = {"water_cc": 1234}
    res = client.put(f'/api/v1/patients/{patient.id}/daily_metrics/{non_existent_date}', json=data, headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 404

def test_update_daily_metric_forbidden(client, setup_metrics):
    """T-4.3: Test a user trying to update another user's metric."""
    patient1 = setup_metrics["patient1"]
    patient2 = setup_metrics["patient2"]
    log_date = date.today() - timedelta(days=2)

    # Log in as patient2
    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_metrics2', 'password': 'password'})
    access_token = login_res.json['data']['token']

    data = {"water_cc": 500}
    # patient2 tries to update patient1's metric
    res = client.put(f'/api/v1/patients/{patient1.id}/daily_metrics/{log_date.strftime("%Y-%m-%d")}', json=data, headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 403

def test_get_daily_metrics_forbidden(client, setup_metrics):
    """T-4.4: Test a user trying to get another user's metrics."""
    patient1 = setup_metrics["patient1"]
    patient2 = setup_metrics["patient2"]

    # Log in as patient2
    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_metrics2', 'password': 'password'})
    access_token = login_res.json['data']['token']

    # patient2 tries to get patient1's metrics
    res = client.get(f'/api/v1/patients/{patient1.id}/daily_metrics', headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 403

def test_get_daily_metrics_pagination(client, setup_metrics):
    """T-4.4: Test pagination for getting daily metrics."""
    patient = setup_metrics["patient1"]

    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_metrics', 'password': 'password'})
    access_token = login_res.json['data']['token']

    res = client.get(f'/api/v1/patients/{patient.id}/daily_metrics?page=1&per_page=2', headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 200
    assert len(res.json['data']) == 2
    assert res.json['pagination']['total_items'] == 5
    assert res.json['pagination']['total_pages'] == 3
    assert res.json['pagination']['current_page'] == 1

    res = client.get(f'/api/v1/patients/{patient.id}/daily_metrics?page=3&per_page=2', headers={'Authorization': f'Bearer {access_token}'})
    assert res.status_code == 200
    assert len(res.json['data']) == 1
    assert res.json['pagination']['current_page'] == 3

def test_create_daily_metric_invalid_data(client, setup_metrics):
    """T-4.2: Test creating a daily metric with invalid data types."""
    patient = setup_metrics["patient1"]

    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_metrics', 'password': 'password'})
    access_token = login_res.json['data']['token']

    data = {
        "water_cc": "not-an-integer",
        "medication": "not-a-boolean",
        "exercise_min": -10, # Negative value
        "cigarettes": "many"
    }

    res = client.post(f'/api/v1/patients/{patient.id}/daily_metrics', json=data, headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 400
    assert 'error' in res.json
    assert res.json['error']['code'] == 'INVALID_INPUT'

# --- Robustness and Error Handling Tests (T-7.3.4) ---

def test_add_metric_invalid_json(client, setup_metrics):
    """T-7.3.4.5: Test POST with invalid JSON body."""
    patient = setup_metrics["patient1"]
    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_metrics', 'password': 'password'})
    access_token = login_res.json['data']['token']

    res = client.post(
        f'/api/v1/patients/{patient.id}/daily_metrics',
        data='{"invalid": "json",}',
        content_type='application/json',
        headers={'Authorization': f'Bearer {access_token}'}
    )
    assert res.status_code == 400
    assert res.json['error']['code'] == 'BAD_REQUEST'

def test_update_metric_invalid_json(client, setup_metrics):
    """T-7.3.4.5: Test PUT with invalid JSON body."""
    patient = setup_metrics["patient1"]
    log_date = (date.today() - timedelta(days=2)).strftime('%Y-%m-%d')
    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_metrics', 'password': 'password'})
    access_token = login_res.json['data']['token']

    res = client.put(
        f'/api/v1/patients/{patient.id}/daily_metrics/{log_date}',
        data='{"invalid": "json",}',
        content_type='application/json',
        headers={'Authorization': f'Bearer {access_token}'}
    )
    assert res.status_code == 400
    assert res.json['error']['code'] == 'BAD_REQUEST'

def test_get_metrics_service_exception(client, setup_metrics, mocker):
    """T-7.3.4.6: Test GET endpoint when service raises an unexpected exception."""
    patient = setup_metrics["patient1"]
    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_metrics', 'password': 'password'})
    access_token = login_res.json['data']['token']

    mocker.patch('app.api.daily_metrics.check_permission', return_value=True)
    mocker.patch('app.api.daily_metrics.DailyMetricService.get_daily_metrics', side_effect=Exception("DB is down"))

    res = client.get(f'/api/v1/patients/{patient.id}/daily_metrics', headers={'Authorization': f'Bearer {access_token}'})
    assert res.status_code == 500
    assert res.json['error']['code'] == 'INTERNAL_SERVER_ERROR'

def test_add_metric_service_exception(client, setup_metrics, mocker):
    """T-7.3.4.6: Test POST endpoint when service raises an unexpected exception."""
    patient = setup_metrics["patient1"]
    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_metrics', 'password': 'password'})
    access_token = login_res.json['data']['token']

    mocker.patch('app.api.daily_metrics.DailyMetricService.create_daily_metric', side_effect=Exception("DB is down"))

    res = client.post(f'/api/v1/patients/{patient.id}/daily_metrics', json={"water_cc": 1}, headers={'Authorization': f'Bearer {access_token}'})
    assert res.status_code == 500
    assert res.json['error']['code'] == 'INTERNAL_SERVER_ERROR'

def test_update_metric_service_exception(client, setup_metrics, mocker):
    """T-7.3.4.6: Test PUT endpoint when service raises an unexpected exception."""
    patient = setup_metrics["patient1"]
    log_date = (date.today() - timedelta(days=2)).strftime('%Y-%m-%d')
    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_metrics', 'password': 'password'})
    access_token = login_res.json['data']['token']

    mocker.patch('app.api.daily_metrics.DailyMetricService.update_daily_metric', side_effect=Exception("DB is down"))

    res = client.put(f'/api/v1/patients/{patient.id}/daily_metrics/{log_date}', json={"water_cc": 1}, headers={'Authorization': f'Bearer {access_token}'})
    assert res.status_code == 500
    assert res.json['error']['code'] == 'INTERNAL_SERVER_ERROR'
