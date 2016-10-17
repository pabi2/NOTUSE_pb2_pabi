# -*- coding: utf-8 -*-

{
    'name': "NSTDA :: PABI2 - Expense Reports",
    'summary': "",
    'author': "Ecosoft",
    'website': "http://ecosoft.co.th",
    'category': 'Account',
    'version': '0.1.0',

    'description': """

Expense Related Reports
=======================

* Dunning Report

    """,
    'depends': [
        'pabi_hr_expense',
    ],
    'data': [
        'views/hr_expense_view.xml',
        'pabi_dunning_letter/wizard/pabi_dunning_letter_wizard.xml',
        'pabi_dunning_letter/data/report_data.xml',
    ],
    'demo': [
    ],
    'installable': True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: