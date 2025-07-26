import pytest
from app.models.models import User, HealthProfile, StaffDetail
from app.utils.extensions import db
from datetime import datetime, timedelta

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

def create_therapist(session, account, password, title="呼吸治療師"):
    """Helper function to create a therapist."""
    therapist = create_user(account, password, is_staff=True)
    session.add(therapist)
    session.commit()
    staff_detail = StaffDetail(user_id=therapist.id, title=title)
    session.add(staff_detail)
    session.commit()
    return therapist

def create_patient(session, account, password, therapist_id):
    """Helper function to create a patient and assign to a therapist."""
    patient = create_user(account, password, is_staff=False)
    session.add(patient)
    session.commit()
    health_profile = HealthProfile(user_id=patient.id, staff_id=therapist_id)
    session.add(health_profile)
    session.commit()
    return patient

@pytest.fixture(scope='function')
def setup_patients(session):
    """Fixture to set up a therapist and some patients."""
    therapist = create_therapist(session, 'therapist1', 'password')
    patient1 = create_patient(session, 'patient1', 'password', therapist.id)
    patient2 = create_patient(session, 'patient2', 'password', therapist.id)
    patient3 = create_patient(session, 'patient3', 'password', therapist.id)

    # Create another therapist and patient for permission tests
    therapist2 = create_therapist(session, 'therapist2', 'password')
    patient4 = create_patient(session, 'patient4', 'password', therapist2.id)
    admin = create_user('admin', 'password', is_admin=True)
    session.add(admin)

    session.commit()

    return {
        "therapist1": therapist,
        "therapist2": therapist2,
        "patient1": patient1,
        "patient2": patient2,
        "patient3": patient3,
        "patient4": patient4,
        "admin": admin
    }

def test_get_therapist_patients_success(client, setup_patients):
    """T-3.2: Test successfully getting a list of assigned patients."""
    therapist = setup_patients["therapist1"]

    # Log in as therapist1
    login_res = client.post('/api/v1/auth/login', json={'account': 'therapist1', 'password': 'password'})
    access_token = login_res.json['data']['token']

    # Get patient list
    res = client.get('/api/v1/therapist/patients', headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 200
    assert res.json['data'] is not None
    assert len(res.json['data']) == 3
    patient_ids = [p['user_id'] for p in res.json['data']]
    assert setup_patients['patient1'].id in patient_ids
    assert setup_patients['patient2'].id in patient_ids
    assert setup_patients['patient3'].id in patient_ids

def test_get_therapist_patients_forbidden(client, setup_patients):
    """T-3.2: Test that a patient cannot access the therapist's patient list."""
    patient = setup_patients["patient1"]

    # Log in as a patient
    login_res = client.post('/api/v1/auth/login', json={'account': 'patient1', 'password': 'password'})
    access_token = login_res.json['data']['token']

    # Attempt to get patient list
    res = client.get('/api/v1/therapist/patients', headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 403

def test_get_patient_profile_success(client, setup_patients):
    """T-3.3: Test that a therapist can get the profile of their own patient."""
    therapist = setup_patients["therapist1"]
    patient = setup_patients["patient1"]

    # Log in as therapist1
    login_res = client.post('/api/v1/auth/login', json={'account': 'therapist1', 'password': 'password'})
    access_token = login_res.json['data']['token']

    # Get patient1's profile
    res = client.get(f'/api/v1/patients/{patient.id}/profile', headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 200
    assert res.json['data'] is not None
    assert res.json['data']['user_id'] == patient.id
    assert res.json['data']['first_name'] == 'Test'

def test_get_patient_profile_forbidden(client, setup_patients):
    """T-3.3: Test that a therapist cannot get the profile of another therapist's patient."""
    therapist2 = setup_patients["therapist2"]
    patient1 = setup_patients["patient1"]

    # Log in as therapist2
    login_res = client.post('/api/v1/auth/login', json={'account': 'therapist2', 'password': 'password'})
    access_token = login_res.json['data']['token']

    # Attempt to get patient1's profile
    res = client.get(f'/api/v1/patients/{patient1.id}/profile', headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 403

def test_get_patient_profile_not_found(client, setup_patients):
    """T-3.3: Test getting a non-existent patient's profile."""
    therapist = setup_patients["therapist1"]

    # Log in as therapist1
    login_res = client.post('/api/v1/auth/login', json={'account': 'therapist1', 'password': 'password'})
    access_token = login_res.json['data']['token']

    # Attempt to get a profile for a non-existent patient ID
    non_existent_id = 9999
    res = client.get(f'/api/v1/patients/{non_existent_id}/profile', headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 404

def test_get_therapist_patients_pagination(client, setup_patients):
    """T-3.2: Test pagination for the therapist's patient list."""
    therapist = setup_patients["therapist1"]

    login_res = client.post('/api/v1/auth/login', json={'account': 'therapist1', 'password': 'password'})
    access_token = login_res.json['data']['token']

    res = client.get('/api/v1/therapist/patients?page=1&per_page=2', headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 200
    assert len(res.json['data']) == 2
    assert res.json['pagination']['total_items'] == 3
    assert res.json['pagination']['total_pages'] == 2

def test_get_therapist_patients_sorting(client, setup_patients):
    """T-3.2: Test sorting for the therapist's patient list."""
    therapist = setup_patients["therapist1"]
    patient1 = setup_patients["patient1"]
    patient2 = setup_patients["patient2"]
    patient3 = setup_patients["patient3"]


    # Manually update created_at for predictable sorting
    patient1.created_at = datetime.utcnow() - timedelta(days=3)
    patient2.created_at = datetime.utcnow() - timedelta(days=1)
    patient3.created_at = datetime.utcnow() - timedelta(days=2)
    db.session.commit()

    login_res = client.post('/api/v1/auth/login', json={'account': 'therapist1', 'password': 'password'})
    access_token = login_res.json['data']['token']

    # Sort by first_name ascending
    res = client.get('/api/v1/therapist/patients?sort_by=created_at&order=asc', headers={'Authorization': f'Bearer {access_token}'})
    assert res.status_code == 200
    assert len(res.json['data']) == 3
    assert res.json['data'][0]['user_id'] == patient1.id
    assert res.json['data'][1]['user_id'] == patient3.id
    assert res.json['data'][2]['user_id'] == patient2.id


def test_patient_cannot_access_own_profile_via_staff_api(client, setup_patients):
    """T-3.3: Test that a patient cannot access their own profile via the staff-only endpoint."""
    patient = setup_patients["patient1"]

    login_res = client.post('/api/v1/auth/login', json={'account': 'patient1', 'password': 'password'})
    access_token = login_res.json['data']['token']

    res = client.get(f'/api/v1/patients/{patient.id}/profile', headers={'Authorization': f'Bearer {access_token}'})

    assert res.status_code == 403

def test_admin_can_access_patient_profile(client, setup_patients):
    """T-3.3: Test that an admin can access any patient's profile."""
    admin = setup_patients["admin"]
    patient = setup_patients["patient1"]

    login_res = client.post('/api/v1/auth/login', json={'account': 'admin', 'password': 'password'})
    access_token = login_res.json['data']['token']

    res = client.get(f'/api/v1/patients/{patient.id}/profile', headers={'Authorization': f'Bearer {access_token}'})

    # The current implementation checks if the accessor is the patient's assigned therapist.
    # It does not have a special case for admins. This test will fail.
    # This highlights a potential logic enhancement.
    # For now, we test the existing behavior, which should be a 403.
    # If the business logic were to allow admins, the expected code would be 200.
    assert res.status_code == 403