# -*- coding: utf-8 -*-
{
    'name': "NSTDA :: PABI2 Budget Preparation",
    'summary': "",
    'author': "Ecosoft",
    'website': "http://ecosoft.co.th",
    'category': 'Account',
    'version': '0.1.0',
    'depends': [
        'account_budget_activity',
        'pabi_chartfield',
        'pabi_procurement',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_budget_prepare_view.xml',
        'workflow/account_budget_prepare_workflow.xml',
    ],
    'demo': [
    ],
    'installable': True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: