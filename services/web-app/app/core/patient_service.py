# services/web-app/app/core/patient_service.py
from .patient_repository import PatientRepository

def get_patients_by_therapist(therapist_id, page, per_page, sort_by, order):
    """
    獲取治療師管理的病患列表。
    """
    repo = PatientRepository()
    paginated_patients = repo.find_all_by_therapist_id(
        therapist_id=therapist_id,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        order=order
    )
    return paginated_patients

def get_patient_profile(patient_id):
    """
    獲取單一病患的詳細檔案。
    """
    repo = PatientRepository()
    return repo.find_profile_by_user_id(patient_id)
