"""FSM holatlar."""
from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    waiting_name = State()          # ism va familiya birga
    waiting_gender = State()
    waiting_birth_date = State()
    waiting_experience = State()
    waiting_photo = State()


class ProfileEdit(StatesGroup):
    waiting_value = State()          # data: {field}


class AddAdmin(StatesGroup):
    waiting_value = State()          # data: {method: id|username|phone}


class UploadTest(StatesGroup):
    waiting_title = State()
    waiting_qpt = State()
    waiting_pass = State()
    waiting_time = State()
    waiting_file = State()


class EditTest(StatesGroup):
    waiting_value = State()  # data: {test_id, field}


class SendTest(StatesGroup):
    choosing_test = State()
    choosing_users = State()  # data: {test_id, selected:set}


class SettingsFSM(StatesGroup):
    waiting_value = State()  # data: {key}


class TakingTest(StatesGroup):
    in_progress = State()
