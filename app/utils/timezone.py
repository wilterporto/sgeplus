from datetime import datetime, timezone, timedelta

def get_brasilia_time():
    """
    Retorna o datetime local atual considerando o fuso horário de Brasília (UTC-3)
    como um objeto datetime naive (sem tzinfo) para compatibilidade com o SQLite/SQLAlchemy.
    """
    tz_brasilia = timezone(timedelta(hours=-3))
    return datetime.now(tz_brasilia).replace(tzinfo=None)
