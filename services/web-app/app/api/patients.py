# services/web-app/app/api/patients.py
from flask import Blueprint, request, jsonify
from flasgger import swag_from
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..core import patient_service
from ..core.user_repository import UserRepository

patients_bp = Blueprint('patients', __name__, url_prefix='/api/v1')

@patients_bp.route('/therapist/patients', methods=['GET'])
@jwt_required()
@swag_from({
    'summary': '獲取管理的病患列表',
    'description': '獲取當前登入的呼吸治療師所管理的所有病患的簡要列表。',
    'tags': ['Patients'],
    'security': [{'bearerAuth': []}],
    'parameters': [
        {'name': 'page', 'in': 'query', 'type': 'integer', 'default': 1, 'description': '頁碼'},
        {'name': 'per_page', 'in': 'query', 'type': 'integer', 'default': 20, 'description': '每頁數量'},
        {'name': 'sort_by', 'in': 'query', 'type': 'string', 'default': 'created_at', 'description': '排序欄位'},
        {'name': 'order', 'in': 'query', 'type': 'string', 'default': 'desc', 'enum': ['asc', 'desc'], 'description': '排序順序'}
    ],
    'responses': {
        '200': {'description': '成功獲取病患列表'},
        '401': {'description': 'Token 無效或未提供'},
        '403': {'description': '沒有治療師權限'}
    }
})
def get_therapist_patients():
    """獲取治療師的病患列表"""
    current_user_id = get_jwt_identity()
    user_repo = UserRepository()
    current_user = user_repo.find_by_id(current_user_id)

    if not current_user or not current_user.is_staff:
        return jsonify({"error": {"code": "PERMISSION_DENIED", "message": "Staff access required"}}), 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    sort_by = request.args.get('sort_by', 'created_at', type=str)
    order = request.args.get('order', 'desc', type=str)

    paginated_data = patient_service.get_patients_by_therapist(
        therapist_id=current_user.id,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        order=order
    )

    # 格式化回傳的資料
    patient_list = []
    for user, health_profile in paginated_data.items:
        patient_info = {
            "user_id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "gender": user.gender,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            # TODO: 待問卷模型完成後，補上 last_cat_score 和 last_mmrc_score
            "last_cat_score": None,
            "last_mmrc_score": None
        }
        patient_list.append(patient_info)

    return jsonify({
        "data": patient_list,
        "pagination": {
            "total_items": paginated_data.total,
            "total_pages": paginated_data.pages,
            "current_page": paginated_data.page,
            "per_page": paginated_data.per_page
        }
    }), 200

@patients_bp.route('/patients/<int:patient_id>/profile', methods=['GET'])
@jwt_required()
@swag_from({
    'summary': '獲取病患詳細健康檔案',
    'description': '獲取指定病患的詳細健康檔案資訊。',
    'tags': ['Patients'],
    'security': [{'bearerAuth': []}],
    'parameters': [
        {'name': 'patient_id', 'in': 'path', 'type': 'integer', 'required': True, 'description': '病患的 user_id'}
    ],
    'responses': {
        '200': {'description': '成功獲取病患檔案'},
        '401': {'description': 'Token 無效或未提供'},
        '403': {'description': '沒有權限查看此病患'},
        '404': {'description': '找不到該病患'}
    }
})
def get_patient_profile(patient_id):
    """獲取病患詳細健康檔案"""
    current_user_id = get_jwt_identity()
    user_repo = UserRepository()
    current_user = user_repo.find_by_id(current_user_id)

    if not current_user or not current_user.is_staff:
        return jsonify({"error": {"code": "PERMISSION_DENIED", "message": "Staff access required"}}), 403

    profile_data = patient_service.get_patient_profile(patient_id)

    if not profile_data:
        return jsonify({"error": {"code": "RESOURCE_NOT_FOUND", "message": "Patient not found"}}), 404

    user, health_profile = profile_data

    # 權限校驗：確保當前治療師是該病患的個管師
    if health_profile.staff_id != current_user.id:
        return jsonify({"error": {"code": "PERMISSION_DENIED", "message": "You are not authorized to view this patient's profile"}}), 403

    # 格式化回傳資料
    response_data = {
        "user_id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "gender": user.gender,
        "email": user.email,
        "phone": user.phone,
        "health_profile": {
            "height_cm": health_profile.height_cm,
            "weight_kg": health_profile.weight_kg,
            "smoke_status": health_profile.smoke_status,
            "updated_at": health_profile.updated_at.isoformat() if health_profile.updated_at else None
        }
    }

    return jsonify({"data": response_data}), 200
