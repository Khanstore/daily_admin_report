{
    'name': 'Daily Admin Report',
    'version': '18.0.0.1',
    'author': 'SM Ashraf',
    'category': 'Reporting',
    'summary': 'Daily business overview (sales, purchase, POS, payments)',
    'depends': ['base', 'sale', 'purchase', 'point_of_sale', 'account'],
    'data': [
        'wizard/business_overview_wizard.xml',
        'report/company_overview_report.xml',
        'security/ir.model.access.csv'
    ],
    'installable': True,
    'application': True,
}
