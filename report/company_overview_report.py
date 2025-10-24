from odoo import models, api

class CompanyOverviewReport(models.AbstractModel):
    _name = 'report.daily_admin_report.company_overview_template'
    _description = 'Company Overview Report Parser'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['business.overview.report'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'business.overview.report',
            'docs': docs,
            'data': data or {},
        }
