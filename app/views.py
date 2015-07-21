from datetime import timedelta
import logging
import json

from flask import request, redirect, flash, Response
from flask.ext.appbuilder.models.sqla.interface import SQLAInterface
from flask.ext.appbuilder import ModelView, CompactCRUDMixin, BaseView, expose
from app import appbuilder, db, models, viz, utils
import config
from wtforms.fields import Field


class ColumnInlineView(CompactCRUDMixin, ModelView):
    datamodel = SQLAInterface(models.Column)
    edit_columns = [
        'column_name', 'description', 'datasource', 'groupby',
        'count_distinct', 'sum', 'min', 'max']
    list_columns = [
        'column_name', 'type', 'groupby', 'count_distinct',
        'sum', 'min', 'max']
    can_delete = False
appbuilder.add_view_no_menu(ColumnInlineView)


class MetricInlineView(CompactCRUDMixin, ModelView):
    datamodel = SQLAInterface(models.Metric)
    list_columns = ['metric_name', 'verbose_name', 'metric_type' ]
    edit_columns = [
        'metric_name', 'description', 'verbose_name', 'metric_type',
        'datasource', 'json']
    add_columns = [
        'metric_name', 'verbose_name', 'metric_type', 'datasource', 'json']
appbuilder.add_view_no_menu(MetricInlineView)


class DatasourceModelView(ModelView):
    datamodel = SQLAInterface(models.Datasource)
    list_columns = ['datasource_link', 'owner', 'is_featured', 'is_hidden']
    related_views = [ColumnInlineView, MetricInlineView]
    edit_columns = [
        'datasource_name', 'description', 'owner', 'is_featured', 'is_hidden',
        'default_endpoint']
    page_size = 100
    order_columns = ['datasource_name']


appbuilder.add_view(
    DatasourceModelView,
    "Datasources",
    icon="fa-cube",
    category_icon='fa-envelope')


class Panoramix(BaseView):
    @expose("/datasource/<datasource_name>/")
    def datasource(self, datasource_name):
        viz_type = request.args.get("viz_type")

        datasource = (
            db.session
            .query(models.Datasource)
            .filter_by(datasource_name=datasource_name)
            .first()
        )
        if not viz_type and datasource.default_endpoint:
            return redirect(datasource.default_endpoint)
        if not viz_type:
            viz_type = "table"
        obj = viz.viz_types[viz_type](
            datasource,
            form_data=request.args, view=self)
        if request.args.get("json"):
            return Response(
                json.dumps(obj.get_query(), indent=4),
                status=200,
                mimetype="application/json")
        if obj.df is None or obj.df.empty:
            return obj.render_no_data()
        return obj.render()


    @expose("/refresh_datasources/")
    def refresh_datasources(self):
        import requests
        endpoint = (
            "http://{COORDINATOR_HOST}:{COORDINATOR_PORT}/"
            "{COORDINATOR_BASE_ENDPOINT}/datasources"
        ).format(**config.__dict__)
        datasources = json.loads(requests.get(endpoint).text)
        for datasource in datasources:
            try:
                models.Datasource.sync_to_db(datasource)
            except Exception as e:
                logging.exception(e)
                logging.error("Failed at syncing " + datasource)
        flash("Refreshed metadata from Druid!", 'info')
        return redirect("/datasourcemodelview/list/")

appbuilder.add_view_no_menu(Panoramix)
appbuilder.add_link(
    "Refresh Metadata",
    href='/panoramix/refresh_datasources/',
    category='Admin',
    icon="fa-cogs")

#models.Metric.__table__.drop(db.engine)
db.create_all()
