# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Guewen Baconnier
#    Copyright 2013 Camptocamp SA
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import logging
from datetime import datetime
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.addons.connector.queue.job import job
from openerp.addons.connector.unit.synchronizer import ExportSynchronizer
from openerp.addons.connector.exception import IDMissingInBackend
from .import_synchronizer import import_record
from ..connector import get_environment

_logger = logging.getLogger(__name__)


"""

Exporters for Prestashop.

In addition to its export job, an exporter has to:

* check in Prestashop if the record has been updated more recently than the
  last sync date and if yes, delay an import
* call the ``bind`` method of the binder to update the last sync date

"""


class PrestashopBaseExporter(ExportSynchronizer):
    """ Base exporter for Prestashop """

    def __init__(self, environment):
        """
        :param environment: current environment (backend, session, ...)
        :type environment: :py:class:`connector.connector.Environment`
        """
        super(PrestashopBaseExporter, self).__init__(environment)
        self.binding_id = None
        self.prestashop_id = None

    def _delay_import(self):
        """ Schedule an import of the record.

        Adapt in the sub-classes when the model is not imported
        using ``import_record``.
        """
        # force is True because the sync_date will be more recent
        # so the import would be skipped
        assert self.prestashop_id
        import_record.delay(self.session, self.model._name,
                            self.backend_record.id, self.prestashop_id,
                            force=True)

    def _should_import(self):
        """ Before the export, compare the update date
        in Prestashop and the last sync date in OpenERP,
        if the former is more recent, schedule an import
        to not miss changes done in Prestashop.
        """
        assert self.binding_record
        if not self.prestashop_id:
            return False
        sync = self.binding_record.sync_date
        if not sync:
            return True
        record = self.backend_adapter.read(self.prestashop_id,
                                           attributes=['updated_at'])

        fmt = DEFAULT_SERVER_DATETIME_FORMAT
        sync_date = datetime.strptime(sync, fmt)
        prestashop_date = datetime.strptime(record['updated_at'], fmt)
        return sync_date < prestashop_date

    def _get_openerp_data(self):
        """ Return the raw OpenERP data for ``self.binding_id`` """
        return self.session.browse(self.model._name, self.binding_id)

    def run(self, binding_id, *args, **kwargs):
        """ Run the synchronization

        :param binding_id: identifier of the binding record to export
        """
        self.binding_id = binding_id
        self.binding_record = self._get_openerp_data()

        self.prestashop_id = self.binder.to_backend(self.binding_id)
        try:
            should_import = self._should_import()
        except IDMissingInBackend:
            self.prestashop_id = None
            should_import = False
        if should_import:
            self._delay_import()

        result = self._run(*args, **kwargs)

        self.binder.bind(self.prestashop_id, self.binding_id)
        return result

    def _run(self):
        """ Flow of the synchronization, implemented in inherited classes"""
        raise NotImplementedError


class PrestashopExporter(PrestashopBaseExporter):
    """ A common flow for the exports to Prestashop """

    def __init__(self, environment):
        """
        :param environment: current environment (backend, session, ...)
        :type environment: :py:class:`connector.connector.Environment`
        """
        super(PrestashopExporter, self).__init__(environment)
        self.binding_record = None

    def _has_to_skip(self):
        """ Return True if the export can be skipped """
        return False

    def _export_dependencies(self):
        """ Export the dependencies for the record"""
        return

    def _map_data(self, fields=None):
        """ Convert the external record to OpenERP """
        self.mapper.convert(self.binding_record, fields=fields)

    def _validate_data(self, data):
        """ Check if the values to import are correct

        Pro-actively check before the ``Model.create`` or
        ``Model.update`` if some fields are missing

        Raise `InvalidDataError`
        """
        return

    def _create(self, data):
        """ Create the Prestashop record """
        return self.backend_adapter.create(data)

    def _update(self, data):
        """ Update an Prestashop record """
        assert self.prestashop_id
        self.backend_adapter.write(self.prestashop_id, data)

    def _run(self, fields=None):
        """ Flow of the synchronization, implemented in inherited classes"""
        assert self.binding_id
        assert self.binding_record

        if not self.prestashop_id:
            fields = None  # should be created with all the fields

        if self._has_to_skip():
            return

        # export the missing linked resources
        self._export_dependencies()

        self._map_data(fields=fields)

        if self.prestashop_id:
            record = self.mapper.data
            if not record:
                return _('Nothing to export.')
            # special check on data before export
            self._validate_data(record)
            self._update(record)
        else:
            record = self.mapper.data_for_create
            if not record:
                return _('Nothing to export.')
            # special check on data before export
            self._validate_data(record)
            self.prestashop_id = self._create(record)
        message = _('Record exported with ID %s on Prestashop.')
        return message % self.prestashop_id


@job
def export_record(session, model_name, binding_id, fields=None):
    """ Export a record on Prestashop """
    record = session.browse(model_name, binding_id)
    env = get_environment(session, model_name, record.backend_id.id)
    exporter = env.get_connector_unit(PrestashopExporter)
    return exporter.run(binding_id, fields=fields)
