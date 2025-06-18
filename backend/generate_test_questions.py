#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для генерации тестовых вопросов в базу данных
"""

import asyncio
import random
from datetime import datetime
from app.db.database import get_database

# Количество вопросов для создания
QUESTIONS_TO_CREATE = 100

# Категории транспортных средств
# CATEGORIES = [
#     ["A1"], ["A"], ["B1"], ["B"], ["BE"], ["C1"], ["C"], ["CE"],
#     ["D1"], ["D"], ["DE"], ["Tm"], ["Tb"], ["BC1"],
#     ["B", "BE"], ["C", "CE"], ["D", "DE"]
# ]
CATEGORIES = [
    ["B"], ["BE"]
]
# Разделы ПДД
PDD_SECTIONS = [
    "polozheniya", "voditeli", "peshehody", "passazhiry", "svetofor", 
    "specsignaly", "avarijka", "manevrirovanie", "raspolozhenie", "speed", 
    "obgon", "ostanovka", "perekrestki", "perehody", "zhd", "magistral", 
    "zhilaya-zona", "prioritet", "svetovye-pribory", "buksirovka", 
    "uchebnaya-ezda", "perevozka-passazhirov", "perevozka-gruzov", 
    "velosipedy-i-zhivotnye", "invalidy", "znaki", "razmetka", "dopusk", 
    "obdzh", "administrativka", "medicina", "dtp", "osnovy-upravleniya"
]

# Шаблоны вопросов
QUESTION_TEMPLATES = [
    {
        "ru": "Разрешается ли водителю {action} в данной ситуации?",
        "kz": "Жүргізушіге {action} осы жағдайда рұқсат етіледі ме?",
        "en": "Is the driver allowed to {action} in this situation?"
    },
    {
        "ru": "Какое действие должен выполнить водитель при {situation}?",
        "kz": "Жүргізуші {situation} кезінде қандай әрекет жасауы керек?",
        "en": "What action should the driver take when {situation}?"
    },
    {
        "ru": "В каком случае запрещается {action}?",
        "kz": "Қандай жағдайда {action} тыйым салынады?",
        "en": "In which case is {action} prohibited?"
    },
    {
        "ru": "Что означает данный дорожный знак?",
        "kz": "Бұл жол белгісі не білдіреді?",
        "en": "What does this road sign mean?"
    },
    {
        "ru": "На каком расстоянии должен остановиться водитель?",
        "kz": "Жүргізуші қандай қашықтықта тоқтауы керек?",
        "en": "At what distance should the driver stop?"
    }
]

# Действия и ситуации для подстановки
ACTIONS = [
    {"ru": "поворачивать налево", "kz": "солға бұрылу", "en": "turn left"},
    {"ru": "обгонять", "kz": "озып өту", "en": "overtake"},
    {"ru": "останавливаться", "kz": "тоқтау", "en": "stop"},
    {"ru": "разворачиваться", "kz": "айналу", "en": "make a U-turn"},
    {"ru": "парковаться", "kz": "тұрақтау", "en": "park"}
]

SITUATIONS = [
    {"ru": "приближении к пешеходному переходу", "kz": "жаяу жүргіншілер өткеліне жақындағанда", "en": "approaching a pedestrian crossing"},
    {"ru": "движении по автомагистрали", "kz": "автомагистральда жүргенде", "en": "driving on a highway"},
    {"ru": "проезде перекрестка", "kz": "қиылысты өткенде", "en": "passing through an intersection"},
    {"ru": "остановке на подъеме", "kz": "көтерілісте тоқтағанда", "en": "stopping on an incline"},
    {"ru": "движении в тумане", "kz": "тұманда жүргенде", "en": "driving in fog"}
]

# Варианты ответов
ANSWER_OPTIONS = [
    [
        {"ru": "Разрешается", "kz": "Рұқсат етіледі", "en": "Allowed"},
        {"ru": "Запрещается", "kz": "Тыйым салынады", "en": "Prohibited"},
        {"ru": "Разрешается только днем", "kz": "Тек күндіз рұқсат етіледі", "en": "Allowed only during daytime"},
        {"ru": "Разрешается с особой осторожностью", "kz": "Ерекше сақтықпен рұқсат етіледі", "en": "Allowed with special caution"}
    ],
    [
        {"ru": "Остановиться", "kz": "Тоқтау", "en": "Stop"},
        {"ru": "Снизить скорость", "kz": "Жылдамдықты азайту", "en": "Reduce speed"},
        {"ru": "Подать звуковой сигнал", "kz": "Дыбыстық сигнал беру", "en": "Sound the horn"},
        {"ru": "Продолжить движение", "kz": "Қозғалысты жалғастыру", "en": "Continue driving"}
    ],
    [
        {"ru": "10 метров", "kz": "10 метр", "en": "10 meters"},
        {"ru": "15 метров", "kz": "15 метр", "en": "15 meters"},
        {"ru": "20 метров", "kz": "20 метр", "en": "20 meters"},
        {"ru": "25 метров", "kz": "25 метр", "en": "25 meters"}
    ],
    [
        {"ru": "Движение запрещено", "kz": "Қозғалыс тыйым салынған", "en": "Traffic prohibited"},
        {"ru": "Остановка запрещена", "kz": "Тоқтау тыйым салынған", "en": "Stopping prohibited"},
        {"ru": "Поворот налево запрещен", "kz": "Солға бұрылу тыйым салынған", "en": "Left turn prohibited"},
        {"ru": "Обгон запрещен", "kz": "Озып өту тыйым салынған", "en": "Overtaking prohibited"}
    ]
]

def generate_uid():
    """Генерирует уникальный UID для вопроса"""
    return f"test_q_{random.randint(100000, 999999)}"

def generate_question_text():
    """Генерирует текст вопроса"""
    template = random.choice(QUESTION_TEMPLATES)
    
    # Если в шаблоне есть подстановки, заменяем их
    if "{action}" in template["ru"]:
        action = random.choice(ACTIONS)
        return {
            "ru": template["ru"].format(action=action["ru"]),
            "kz": template["kz"].format(action=action["kz"]),
            "en": template["en"].format(action=action["en"])
        }
    elif "{situation}" in template["ru"]:
        situation = random.choice(SITUATIONS)
        return {
            "ru": template["ru"].format(situation=situation["ru"]),
            "kz": template["kz"].format(situation=situation["kz"]),
            "en": template["en"].format(situation=situation["en"])
        }
    else:
        return template

def generate_options():
    """Генерирует варианты ответов с метками A, B, C, D"""
    options_set = random.choice(ANSWER_OPTIONS)
    labels = ["A", "B", "C", "D"]
    
    options_with_labels = []
    for i, option in enumerate(options_set):
        options_with_labels.append({
            "label": labels[i],
            "text": option
        })
    
    return options_with_labels

def generate_explanation():
    """Генерирует объяснение к вопросу"""
    explanations = [
        {
            "ru": "Согласно правилам дорожного движения, данное действие регулируется соответствующими пунктами ПДД.",
            "kz": "Жол қозғалысы ережелеріне сәйкес, бұл әрекет ЖҚЕ-нің тиісті тармақтарымен реттеледі.",
            "en": "According to traffic rules, this action is regulated by the corresponding clauses of the traffic code."
        },
        {
            "ru": "В данной ситуации водитель должен руководствоваться принципами безопасности дорожного движения.",
            "kz": "Бұл жағдайда жүргізуші жол қозғалысы қауіпсіздігінің принциптерін басшылыққа алуы керек.",
            "en": "In this situation, the driver should be guided by the principles of road safety."
        },
        {
            "ru": "Правильный ответ основан на требованиях дорожных знаков и разметки.",
            "kz": "Дұрыс жауап жол белгілері мен белгілеулердің талаптарына негізделген.",
            "en": "The correct answer is based on the requirements of road signs and markings."
        }
    ]
    
    return random.choice(explanations)

async def create_test_questions(count: int):
    """Создает тестовые вопросы в базе данных"""
    db = await get_database()
    
    print(f"Создание {count} тестовых вопросов...")
    
    questions_created = 0
    
    for i in range(count):
        try:
            # Генерируем данные вопроса
            question_text = generate_question_text()
            options = generate_options()
            correct_label = random.choice(["A", "B", "C", "D"])
            categories = random.choice(CATEGORIES)
            pdd_sections = random.sample(PDD_SECTIONS, random.randint(2, 5))
            explanation = generate_explanation()
            uid = generate_uid()
            
            # Проверяем, что такого UID еще нет
            existing = await db.questions.find_one({"uid": uid})
            if existing:
                uid = f"{uid}_{i}"
            
            question_dict = {
                "question_text": question_text,
                "options": options,
                "correct_label": correct_label,
                "categories": categories,
                "pdd_section_uids": pdd_sections,
                "created_by_name": "Test Generator",
                "created_by_iin": "000000000000",
                "uid": uid,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": None,
                "deleted": False,
                "deleted_by": None,
                "deleted_at": None,
                "media_file_id": None,
                "media_filename": None,
                "after_answer_media_file_id": None,
                "after_answer_media_id": None,
                "after_answer_media_filename": None,
                "explanation": explanation,
                # Флаги наличия медиа
                "has_media": False,
                "has_after_answer_media": False,
                "has_after_media": False
            }
            
            # Вставляем в базу данных
            result = await db.questions.insert_one(question_dict)
            
            if result.inserted_id:
                questions_created += 1
                if questions_created % 10 == 0:
                    print(f"Создано {questions_created} вопросов...")
            
        except Exception as e:
            print(f"Ошибка при создании вопроса {i+1}: {e}")
            continue
    
    print(f"Успешно создано {questions_created} из {count} вопросов")
    
    # Показываем статистику по категориям
    print("\nСтатистика по категориям:")
    for category_set in CATEGORIES:
        count = await db.questions.count_documents({
            "deleted": False,
            "categories": {"$in": category_set}
        })
        print(f"  {', '.join(category_set)}: {count} вопросов")

async def main():
    """Главная функция"""
    print("=== Генератор тестовых вопросов ===")
    print(f"Будет создано {QUESTIONS_TO_CREATE} вопросов")
    
    # Подключаемся к базе данных
    try:
        db = await get_database()
        
        # Проверяем текущее количество вопросов
        current_count = await db.questions.count_documents({"deleted": False})
        print(f"Текущее количество вопросов в базе: {current_count}")
        
        # Создаем тестовые вопросы
        await create_test_questions(QUESTIONS_TO_CREATE)
        
        # Проверяем итоговое количество
        final_count = await db.questions.count_documents({"deleted": False})
        print(f"Итоговое количество вопросов в базе: {final_count}")
        print(f"Добавлено: {final_count - current_count} вопросов")
        
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 