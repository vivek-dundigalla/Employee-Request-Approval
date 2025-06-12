{
    'name': 'Employee Request Approval',
    'version': '18.0.1.0',
    'category': 'Human Resources',
    'summary': 'Allows employees to submit requests and get approval from HR or Manager with report printing and chatter tracking.',
    'description': """
        - Employees can submit various types of requests.
        - HR or Managers can approve or reject.
        - Chatter shows approval details.
        - Report can be printed after approval.
    """,
    'author': 'sidmec technologies',
    'depends': ['base', 'hr', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/group.xml',
        'data/sequence.xml',
        # 'data/mail_template.xml',
        'views/employee_request_view.xml',
        'report/request_report_template.xml',
        "report/response_report_template.xml",
        "views/menu.xml",
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
