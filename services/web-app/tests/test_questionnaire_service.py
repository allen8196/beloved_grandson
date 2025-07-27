# services/web-app/tests/test_questionnaire_service.py
import pytest
from app.core.questionnaire_service import QuestionnaireService
from unittest.mock import MagicMock
from datetime import date

class TestCalculateCatScore:
    """T-7.2.2: Unit tests for the _calculate_cat_score method."""

    @pytest.fixture
    def service(self):
        """Provides an instance of the QuestionnaireService."""
        return QuestionnaireService()

    def test_calculate_cat_score_all_zeros(self, service):
        """Test calculation when all scores are 0."""
        data = {
            'cough_score': 0, 'phlegm_score': 0, 'chest_score': 0, 'breath_score': 0,
            'limit_score': 0, 'confidence_score': 0, 'sleep_score': 0, 'energy_score': 0
        }
        assert service._calculate_cat_score(data) == 0

    def test_calculate_cat_score_all_max(self, service):
        """Test calculation when all scores are the maximum value (5)."""
        data = {
            'cough_score': 5, 'phlegm_score': 5, 'chest_score': 5, 'breath_score': 5,
            'limit_score': 5, 'confidence_score': 5, 'sleep_score': 5, 'energy_score': 5
        }
        assert service._calculate_cat_score(data) == 40

    def test_calculate_cat_score_mixed_values(self, service):
        """Test calculation with a mix of different valid scores."""
        data = {
            'cough_score': 1, 'phlegm_score': 2, 'chest_score': 3, 'breath_score': 4,
            'limit_score': 5, 'confidence_score': 0, 'sleep_score': 1, 'energy_score': 2
        }
        assert service._calculate_cat_score(data) == 18

    def test_calculate_cat_score_missing_fields(self, service):
        """Test calculation when some score fields are missing from the input data."""
        data = {
            'cough_score': 3,
            'energy_score': 4
        }
        # It should treat missing fields as 0
        assert service._calculate_cat_score(data) == 7

@pytest.fixture
def mocked_service(mocker):
    """Provides a QuestionnaireService instance with mocked repositories for broader use."""
    service = QuestionnaireService()
    mocker.patch.object(service, 'questionnaire_repo', autospec=True)
    mocker.patch.object(service, 'user_repo', autospec=True)
    return service

class TestSubmitCatQuestionnaire:
    """T-7.2.2: Unit tests for the submit_cat_questionnaire method."""

    def test_submit_cat_questionnaire_success(self, mocked_service):
        """Test the successful submission of a CAT questionnaire."""
        patient_id = 1
        mock_patient = MagicMock()
        mock_patient.is_staff = False
        
        mocked_service.user_repo.find_by_id.return_value = mock_patient
        mocked_service.questionnaire_repo.find_cat_by_user_id_and_month.return_value = None
        
        mock_new_record = MagicMock()
        mocked_service.questionnaire_repo.create_cat_record.return_value = mock_new_record

        today_str = date.today().isoformat()
        data = {
            "record_date": today_str,
            'cough_score': 1, 'phlegm_score': 1, 'chest_score': 1, 'breath_score': 1,
            'limit_score': 1, 'confidence_score': 1, 'sleep_score': 1, 'energy_score': 1
        }

        new_record, error = mocked_service.submit_cat_questionnaire(patient_id, data)

        assert error is None
        assert new_record == mock_new_record
        mocked_service.user_repo.find_by_id.assert_called_once_with(patient_id)
        mocked_service.questionnaire_repo.find_cat_by_user_id_and_month.assert_called_once()
        mocked_service.questionnaire_repo.create_cat_record.assert_called_once()

    def test_submit_cat_patient_not_found(self, mocked_service):
        """Test submission when the patient_id does not exist."""
        mocked_service.user_repo.find_by_id.return_value = None
        
        new_record, error = mocked_service.submit_cat_questionnaire(999, {"record_date": "2025-07-27", 'cough_score': 1, 'phlegm_score': 1, 'chest_score': 1, 'breath_score': 1, 'limit_score': 1, 'confidence_score': 1, 'sleep_score': 1, 'energy_score': 1})
        
        assert new_record is None
        assert error == "Patient not found."
        mocked_service.user_repo.find_by_id.assert_called_once_with(999)
        mocked_service.questionnaire_repo.find_cat_by_user_id_and_month.assert_not_called()

    def test_submit_cat_record_already_exists(self, mocked_service):
        """Test submission when a record for the given month already exists."""
        patient_id = 1
        mock_patient = MagicMock()
        mock_patient.is_staff = False
        
        mocked_service.user_repo.find_by_id.return_value = mock_patient
        mocked_service.questionnaire_repo.find_cat_by_user_id_and_month.return_value = MagicMock()
        
        today_str = date.today().isoformat()
        data = {
            "record_date": today_str,
            'cough_score': 1, 'phlegm_score': 1, 'chest_score': 1, 'breath_score': 1,
            'limit_score': 1, 'confidence_score': 1, 'sleep_score': 1, 'energy_score': 1
        }

        new_record, error = mocked_service.submit_cat_questionnaire(patient_id, data)

        assert new_record is None
        assert "already exists" in error
        mocked_service.questionnaire_repo.create_cat_record.assert_not_called()

    def test_submit_cat_invalid_date_format(self, mocked_service):
        """Test submission with an invalid date format string."""
        patient_id = 1
        mock_patient = MagicMock()
        mock_patient.is_staff = False
        mocked_service.user_repo.find_by_id.return_value = mock_patient

        data = {"record_date": "2025-07-27T10:00:00", 'cough_score': 1, 'phlegm_score': 1, 'chest_score': 1, 'breath_score': 1, 'limit_score': 1, 'confidence_score': 1, 'sleep_score': 1, 'energy_score': 1}

        new_record, error = mocked_service.submit_cat_questionnaire(patient_id, data)

        assert new_record is None
        assert error == "Invalid or missing record_date."
        mocked_service.questionnaire_repo.find_cat_by_user_id_and_month.assert_not_called()

class TestUpdateCatQuestionnaire:
    """T-7.2.2: Unit tests for the update_cat_questionnaire method."""

    def test_update_cat_success(self, mocked_service):
        """Test the successful update of a CAT questionnaire."""
        patient_id = 1
        year, month = 2025, 7
        mock_patient = MagicMock()
        mock_patient.is_staff = False
        mock_existing_record = MagicMock()
        
        mocked_service.user_repo.find_by_id.return_value = mock_patient
        mocked_service.questionnaire_repo.find_cat_by_user_id_and_month.return_value = mock_existing_record
        mocked_service.questionnaire_repo.update_cat_record.return_value = mock_existing_record

        data = {'cough_score': 2, 'phlegm_score': 2, 'chest_score': 2, 'breath_score': 2, 'limit_score': 2, 'confidence_score': 2, 'sleep_score': 2, 'energy_score': 2}
        
        updated_record, error = mocked_service.update_cat_questionnaire(patient_id, year, month, data)

        assert error is None
        assert updated_record == mock_existing_record
        mocked_service.questionnaire_repo.update_cat_record.assert_called_once()

    def test_update_cat_record_not_found(self, mocked_service):
        """Test updating when no record is found for the given month."""
        patient_id = 1
        year, month = 2025, 7
        mock_patient = MagicMock()
        mock_patient.is_staff = False

        mocked_service.user_repo.find_by_id.return_value = mock_patient
        mocked_service.questionnaire_repo.find_cat_by_user_id_and_month.return_value = None

        data = {'cough_score': 2}
        updated_record, error = mocked_service.update_cat_questionnaire(patient_id, year, month, data)

        assert updated_record is None
        assert "No CAT record found" in error
        mocked_service.questionnaire_repo.update_cat_record.assert_not_called()

class TestSubmitMmrcQuestionnaire:
    """T-7.2.2: Unit tests for the submit_mmrc_questionnaire method."""

    def test_submit_mmrc_success(self, mocked_service):
        """Test the successful submission of an MMRC questionnaire."""
        patient_id = 1
        mock_patient = MagicMock()
        mock_patient.is_staff = False
        
        mocked_service.user_repo.find_by_id.return_value = mock_patient
        mocked_service.questionnaire_repo.find_mmrc_by_user_id_and_month.return_value = None
        mocked_service.questionnaire_repo.create_mmrc_record.return_value = MagicMock()

        data = {"record_date": "2025-07-27", "score": 2, "answer_text": "Test"}
        new_record, error = mocked_service.submit_mmrc_questionnaire(patient_id, data)

        assert error is None
        mocked_service.questionnaire_repo.create_mmrc_record.assert_called_once()

    def test_submit_mmrc_invalid_score(self, mocked_service):
        """Test submission with an out-of-range MMRC score."""
        patient_id = 1
        mock_patient = MagicMock()
        mock_patient.is_staff = False
        mocked_service.user_repo.find_by_id.return_value = mock_patient

        data = {"record_date": "2025-07-27", "score": 5, "answer_text": "Invalid"}
        new_record, error = mocked_service.submit_mmrc_questionnaire(patient_id, data)

        assert new_record is None
        assert "Invalid score" in error
        mocked_service.questionnaire_repo.create_mmrc_record.assert_not_called()

class TestUpdateMmrcQuestionnaire:
    """T-7.2.2: Unit tests for the update_mmrc_questionnaire method."""

    def test_update_mmrc_success(self, mocked_service):
        """Test the successful update of an MMRC questionnaire."""
        patient_id = 1
        year, month = 2025, 7
        mock_patient = MagicMock()
        mock_patient.is_staff = False
        mock_existing_record = MagicMock()

        mocked_service.user_repo.find_by_id.return_value = mock_patient
        mocked_service.questionnaire_repo.find_mmrc_by_user_id_and_month.return_value = mock_existing_record
        mocked_service.questionnaire_repo.update_mmrc_record.return_value = mock_existing_record

        data = {"score": 3, "answer_text": "Updated"}
        updated_record, error = mocked_service.update_mmrc_questionnaire(patient_id, year, month, data)

        assert error is None
        assert updated_record == mock_existing_record
        mocked_service.questionnaire_repo.update_mmrc_record.assert_called_once()

    def test_update_mmrc_record_not_found(self, mocked_service):
        """Test updating when no MMRC record is found for the given month."""
        patient_id = 1
        year, month = 2025, 7
        mock_patient = MagicMock()
        mock_patient.is_staff = False

        mocked_service.user_repo.find_by_id.return_value = mock_patient
        mocked_service.questionnaire_repo.find_mmrc_by_user_id_and_month.return_value = None

        data = {"score": 3}
        updated_record, error = mocked_service.update_mmrc_questionnaire(patient_id, year, month, data)

        assert updated_record is None
        assert "No MMRC record found" in error
        mocked_service.questionnaire_repo.update_mmrc_record.assert_not_called()
