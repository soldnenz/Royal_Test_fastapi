"""
Инициализация индексов MongoDB (упрощённо: без дат и без составных индексов)
"""
from app.logging import get_logger, LogSection, LogSubsection
from pymongo import IndexModel

logger = get_logger("database_indexes")


async def create_database_indexes(db):
    logger.info(
        section=LogSection.DATABASE,
        subsection=LogSubsection.DATABASE.INDEXES_CREATE,
        message="Начинаем создание индексов базы данных"
    )

    try:
        await db.questions.create_indexes([
            IndexModel([("uid", 1)], name="uid_uniq", unique=True),

            # Активные по категориям/разделам (без сортировки по дате)
            IndexModel([("categories", 1)],
                       name="by_cat_active",
                       partialFilterExpression={"deleted": False}),
            IndexModel([("pdd_section_uids", 1)],
                       name="by_section_active",
                       partialFilterExpression={"deleted": False}),

            # Флаг удалённости (для быстрых выборок удалённых)
            IndexModel([("deleted", 1)],
                       name="deleted_flag",
                       partialFilterExpression={"deleted": True}),
        ])
        logger.info(section=LogSection.DATABASE,
                    subsection=LogSubsection.DATABASE.INDEXES_SUCCESS,
                    message="Индексы для коллекции questions созданы")

        # -------------------------
        # lobbies (только одиночные индексы)
        await db.lobbies.create_indexes([
            IndexModel([("host_id", 1)], name="host_id"),
            IndexModel([("status", 1)], name="status"),
            IndexModel([("exam_mode", 1)], name="exam_mode"),
            # Если понадобятся тяжёлые выборки по участникам — включишь позже:
            # IndexModel([("participants", 1)], name="participants")
        ])
        logger.info(section=LogSection.DATABASE,
                    subsection=LogSubsection.DATABASE.INDEXES_SUCCESS,
                    message="Индексы для коллекции lobbies созданы")

        # -------------------------
        # users (одиночные индексы + уникальность)
        await db.users.create_indexes([
            IndexModel([("iin", 1)], name="iin_uniq", unique=True),

            # email: уникальный только для непустых строк
            IndexModel(
                [("email", 1)],
                name="email_uniq",
                unique=True,
                partialFilterExpression={"email": {"$exists": True, "$type": "string", "$gt": ""}}
            ),

            # phone: уникальный только для непустых строк
            IndexModel(
                [("phone", 1)],
                name="phone_uniq",
                unique=True,
                partialFilterExpression={"phone": {"$exists": True, "$type": "string", "$gt": ""}}
            ),

            IndexModel(
                [("referred_by", 1)],
                name="referred_by_only",
                partialFilterExpression={"referred_by": {"$exists": True}}
            ),
        ])
        logger.info(section=LogSection.DATABASE,
                    subsection=LogSubsection.DATABASE.INDEXES_SUCCESS,
                    message="Индексы для коллекции users созданы")

        # -------------------------
        # tokens (одиночные)
        await db.tokens.create_indexes([
            IndexModel([("token", 1)], name="token_uniq", unique=True),
            IndexModel([("user_id", 1)], name="by_user"),
            IndexModel([("expires_at", 1)], name="ttl", expireAfterSeconds=0),  # автоудаление по времени
        ])
        logger.info(section=LogSection.DATABASE,
                    subsection=LogSubsection.DATABASE.INDEXES_SUCCESS,
                    message="Индексы для коллекции tokens созданы")

        # -------------------------
        # subscriptions (одиночные)
        await db.subscriptions.create_indexes([
            IndexModel([("user_id", 1)], name="subs_by_user"),
            IndexModel([("is_active", 1)], name="subs_is_active"),
        ])
        logger.info(section=LogSection.DATABASE,
                    subsection=LogSubsection.DATABASE.INDEXES_SUCCESS,
                    message="Индексы для коллекции subscriptions созданы")

        logger.info(section=LogSection.DATABASE,
                    subsection=LogSubsection.DATABASE.INDEXES_SUCCESS,
                    message="Все индексы базы данных успешно созданы")

    except Exception as e:
        logger.error(
            section=LogSection.DATABASE,
            subsection=LogSubsection.DATABASE.INDEXES_ERROR,
            message=f"Ошибка при создании индексов: {str(e)}"
        )
        raise
