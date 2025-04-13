# app/utils/answers.py
def check_answer(correct_answers_map: dict, question_id: str, user_answer: int) -> bool:
    """
    Возвращает True, если ответ пользователя с индексом `user_answer`
    соответствует правильному ответу на вопрос `question_id` в словаре correct_answers_map.
    """
    if question_id not in correct_answers_map:
        return False  # вопрос не найден
    return correct_answers_map[question_id] == user_answer