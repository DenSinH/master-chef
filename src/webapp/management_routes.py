import sanic
from sanic import Sanic, Request
import datetime
import auth
from data.models import *
import data
from sqlalchemy import select


# endpoint name -> sqlalchemy model mapping
TABLES = {
    "users": User,
    "comments": Comment,
    "saves": Save
}


def convert_field(field):
    """ Convert a sqlalchmy field to something that can be
        rendered properly in HTML """
    if isinstance(field, (datetime.datetime, datetime.date)):
        return str(field)
    return field


def to_dict(row):
    """ Convert sqlalchemy object columns """
    return {
        col.name: convert_field(getattr(row, col.name))
        for col in row.__table__.columns
    }


def col_type(col):
    """ Get column type as string """
    if isinstance(col.type, Boolean):
        return "boolean"
    if isinstance(col.type, Integer):
        if col.nullable:
            return "intnull"
        return "integer"
    if isinstance(col.type, DateTime):
        if col.nullable:
            return "datetimenull"
        return "datetime"
    if col.nullable:
        return "stringnull"
    return "string"


def add_management_routes(app: Sanic):
    """ Add data-management routes """

    @app.route("/manage/<table_name>")
    @app.ext.template("/manage/table.html")
    @auth.protected("admin")
    async def manage(request, table_name):
        """ Data management table view """
        return {
            "columns": list([col.name for col in TABLES[table_name].__table__.columns]),
            "column_types": {
                col.name: col_type(col)
                for col in TABLES[table_name].__table__.columns
            },
            "table_name": table_name
        }


    @app.get("/api/<table_name>")
    @auth.protected("admin")
    async def api_get_all(request, table_name):
        """ Data management table contents """
        async with data.Session() as session:
            table_class = TABLES[table_name]
            result = await session.execute(select(table_class))
            return sanic.json({
                "data": [to_dict(row) for row in result.scalars().all()]
            })


    @app.get("/api/<table_name>/<id>")
    @auth.protected("admin")
    async def api_get_one(request, table_name, id: int):
        """ Data management get single row by id """
        async with data.Session() as session:
            table_class = TABLES[table_name]
            result = await session.execute(select(table_class).where(table_class.id == id))
            obj = result.scalar()
            if obj:
                return sanic.json({"data": to_dict(obj)})
            else:
                return sanic.json({"error": "Not found"}, status=404)


    @app.post("/api/<table_name>")
    @auth.protected("admin")
    async def api_create(request: Request, table_name):
        """ Data management create row """
        async with data.Session() as session:
            table_class = TABLES[table_name]
            obj_data = request.json

            # convert datetime columns
            for col, val in obj_data.items():
                if isinstance(table_class.__table__.columns[col], (DateTime,)):
                    if isinstance(val, (int, float)):
                        obj_data[col] = datetime.datetime.utcfromtimestamp(val / 1000)
            
            # create instance
            obj = table_class(**obj_data)
            session.add(obj)
            res_data = to_dict(obj)
            await session.commit()
            return sanic.json({"data": res_data})


    @app.put("/api/<table_name>/<id>")
    @auth.protected("admin")
    async def api_update(request, table_name, id: int):
        """ Data management update single row """
        async with data.Session() as session:
            table_class = TABLES[table_name]
            result = await session.execute(select(table_class).where(table_class.id == id))
            obj = result.scalar()

            if obj:
                # convert datetime columns
                for key, value in request.json.items():
                    if isinstance(table_class.__table__.columns[key].type, (DateTime,)):
                        if isinstance(value, (int, float)):
                            value = datetime.datetime.utcfromtimestamp(value / 1000)
                    
                    # update object
                    setattr(obj, key, value)
                res_data = to_dict(obj)
                await session.commit()
                return sanic.json({"data": res_data})
            else:
                return sanic.json({"error": "Not found"}, status=404)


    @app.delete("/api/<table_name>/<id>")
    @auth.protected("admin")
    async def api_delete(request, table_name, id: int):
        """ Data management delete single row """
        async with data.Session() as session:
            table_class = TABLES[table_name]
            result = await session.execute(select(table_class).where(table_class.id == id))
            obj = result.scalar()
            if obj:
                await session.delete(obj)
                await session.commit()
                return sanic.json({"message": "Deleted successfully"})
            else:
                return sanic.json({"error": "Not found"}, status=404)
