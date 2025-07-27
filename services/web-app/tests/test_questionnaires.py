# services/web-app/tests/test_questionnaires.py
import pytest
from datetime import date, datetime, timedelta
from app.models.models import User, HealthProfile, QuestionnaireCAT, QuestionnaireMMRC
from app.extensions import db


class TestQuestionnairePermissions:
    """T-7.2.1: Test suite for questionnaire API permissions."""

    @pytest.mark.parametrize("method, path_template", [
        ("GET", "/api/v1/patients/{patient_id}/questionnaires/cat"),
        ("POST", "/api/v1/patients/{patient_id}/questionnaires/cat"),
        ("PUT", "/api/v1/patients/{patient_id}/questionnaires/cat/2025/7"),
        ("GET", "/api/v1/patients/{patient_id}/questionnaires/mmrc"),
        ("POST", "/api/v1/patients/{patient_id}/questionnaires/mmrc"),
        ("PUT", "/api/v1/patients/{patient_id}/questionnaires/mmrc/2025/7"),
    ])
    def test_unauthenticated_access_is_denied(self, client, setup_questionnaires, method, path_template):
        """T-7.2.1: Ensure unauthenticated users receive a 401 Unauthorized error."""
        patient = setup_questionnaires["patient1"]
        path = path_template.format(patient_id=patient.id)

        if method == "GET":
            res = client.get(path)
        elif method == "POST":
            res = client.post(path, json={})
        elif method == "PUT":
            res = client.put(path, json={})

        assert res.status_code == 401, f"Expected 401 for {method} {path}, but got {res.status_code}"
        assert "Missing Authorization Header" in res.json['msg']


    @pytest.mark.parametrize("method, path_template", [
        ("GET", "/api/v1/patients/{patient_id}/questionnaires/cat"),
        ("POST", "/api/v1/patients/{patient_id}/questionnaires/cat"),
        ("PUT", "/api/v1/patients/{patient_id}/questionnaires/cat/2025/7"),
        ("GET", "/api/v1/patients/{patient_id}/questionnaires/mmrc"),
        ("POST", "/api/v1/patients/{patient_id}/questionnaires/mmrc"),
        ("PUT", "/api/v1/patients/{patient_id}/questionnaires/mmrc/2025/7"),
    ])
    def test_forbidden_access_is_denied(self, client, setup_questionnaires, method, path_template):
        """T-7.2.1: Ensure users cannot access other patients' data."""
        # patient_q logs in
        login_res = client.post('/api/v1/auth/login', json={'account': 'patient_q', 'password': 'password'})
        access_token = login_res.json['data']['token']
        headers = {'Authorization': f'Bearer {access_token}'}

        # But tries to access patient_q2's data
        patient2 = setup_questionnaires["patient2"]
        path = path_template.format(patient_id=patient2.id)

        if method == "GET":
            res = client.get(path, headers=headers)
        elif method == "POST":
            res = client.post(path, json={}, headers=headers)
        elif method == "PUT":
            res = client.put(path, json={}, headers=headers)

        assert res.status_code == 403, f"Expected 403 for {method} {path}, but got {res.status_code}"
        assert "You are not authorized to access this resource" in res.json['error']['message']


class TestQuestionnaireValidation:
    """T-7.2.1: Test suite for questionnaire data validation."""

    def test_submit_cat_with_invalid_score_is_rejected(self, client, setup_questionnaires):
        """T-7.2.1: Ensure submitting a CAT with out-of-range scores returns a 400 error."""
        patient = setup_questionnaires["patient1"]

        login_res = client.post('/api/v1/auth/login', json={'account': 'patient_q', 'password': 'password'})
        access_token = login_res.json['data']['token']
        headers = {'Authorization': f'Bearer {access_token}'}

        today_str = date.today().isoformat()
        # One score is invalid (e.g., 6, which is > 5)
        data = {
            "record_date": today_str,
            "cough_score": 1, "phlegm_score": 1, "chest_score": 1, "breath_score": 1,
            "limit_score": 1, "confidence_score": 1, "sleep_score": 1, "energy_score": 6
        }

        res = client.post(f'/api/v1/patients/{patient.id}/questionnaires/cat', json=data, headers=headers)

        assert res.status_code == 400
        assert "Invalid score" in res.json['error']['message']

    def test_submit_mmrc_with_invalid_score_is_rejected(self, client, setup_questionnaires):
        """T-7.2.1: Ensure submitting an MMRC with an out-of-range score returns a 400 error."""
        patient = setup_questionnaires["patient1"]

        login_res = client.post('/api/v1/auth/login', json={'account': 'patient_q', 'password': 'password'})
        access_token = login_res.json['data']['token']
        headers = {'Authorization': f'Bearer {access_token}'}

        today_str = date.today().isoformat()
        # Score is invalid (e.g., 5, which is > 4)
        data = {
            "record_date": today_str,
            "score": 5,
            "answer_text": "Invalid score test"
        }

        res = client.post(f'/api/v1/patients/{patient.id}/questionnaires/mmrc', json=data, headers=headers)

        assert res.status_code == 400
        assert "Invalid score" in res.json['error']['message']


# Helper functions from other test files can be consolidated later
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
def setup_questionnaires(session):
    """Fixture to set up patients and some questionnaire records."""
    patient1 = create_patient(session, 'patient_q', 'password')
    patient2 = create_patient(session, 'patient_q2', 'password')

    # Create a CAT record for patient1 for last month
    last_month_date = date.today().replace(day=1) - timedelta(days=1)
    cat_record = QuestionnaireCAT(
        user_id=patient1.id,
        record_date=last_month_date,
        cough_score=1, phlegm_score=2, chest_score=3, breath_score=4,
        limit_score=1, confidence_score=2, sleep_score=3, energy_score=4,
        total_score=20
    )
    session.add(cat_record)

    # Create an MMRC record for patient1 for last month
    mmrc_record = QuestionnaireMMRC(
        user_id=patient1.id,
        record_date=last_month_date,
        score=2,
        answer_text="I walk slower than people of the same age on the level because of breathlessness, or have to stop for breath when walking at my own pace on the level."
    )
    session.add(mmrc_record)

    session.commit()

    return {
        "patient1": patient1,
        "patient2": patient2,
        "last_month": last_month_date
    }

# TODO: Add test cases for CAT and MMRC questionnaires

#<editor-fold desc="CAT Questionnaire Tests">
def test_submit_cat_success(client, setup_questionnaires):
    """T-5.1: Test successfully submitting a new CAT questionnaire."""
    patient = setup_questionnaires["patient1"]

    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_q', 'password': 'password'})
    access_token = login_res.json['data']['token']

    today_str = date.today().isoformat()
    data = {
        "record_date": today_str,
        "cough_score": 1, "phlegm_score": 1, "chest_score": 1, "breath_score": 1,
        "limit_score": 1, "confidence_score": 1, "sleep_score": 1, "energy_score": 1
    }

    res = client.post(f'/api/v1/patients/{patient.id}/questionnaires/cat', json=data, headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 201
    assert res.json['data']['total_score'] == 8
    assert "record_id" in res.json['data']

def test_submit_cat_conflict(client, setup_questionnaires):
    """T-5.1: Test submitting a CAT questionnaire for a month that already has one."""
    patient = setup_questionnaires["patient1"]
    last_month = setup_questionnaires["last_month"]

    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_q', 'password': 'password'})
    access_token = login_res.json['data']['token']

    # Try to submit another questionnaire for last month
    data = {
        "record_date": last_month.isoformat(),
        "cough_score": 2, "phlegm_score": 2, "chest_score": 2, "breath_score": 2,
        "limit_score": 2, "confidence_score": 2, "sleep_score": 2, "energy_score": 2
    }

    res = client.post(f'/api/v1/patients/{patient.id}/questionnaires/cat', json=data, headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 409
    assert "already exists" in res.json['error']['message']

def test_update_cat_success(client, setup_questionnaires):
    """T-5.2: Test successfully updating an existing CAT questionnaire."""
    patient = setup_questionnaires["patient1"]
    last_month = setup_questionnaires["last_month"]

    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_q', 'password': 'password'})
    access_token = login_res.json['data']['token']

    data = {
        "record_date": last_month.isoformat(),
        "cough_score": 5, "phlegm_score": 5, "chest_score": 5, "breath_score": 5,
        "limit_score": 5, "confidence_score": 5, "sleep_score": 5, "energy_score": 5
    }

    res = client.put(f'/api/v1/patients/{patient.id}/questionnaires/cat/{last_month.year}/{last_month.month}', json=data, headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 200
    assert res.json['data']['total_score'] == 40

def test_get_cat_history_success(client, setup_questionnaires):
    """T-5.3: Test successfully getting CAT history."""
    patient = setup_questionnaires["patient1"]

    login_res = client.post('/api/v1/auth/login', json={'account': 'patient_q', 'password': 'password'})
    access_token = login_res.json['data']['token']

    res = client.get(f'/api/v1/patients/{patient.id}/questionnaires/cat', headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 200
    assert len(res.json['data']) == 1
    assert res.json['data'][0]['total_score'] == 20
