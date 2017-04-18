# -*- coding: utf-8 -*-
from openerp import tools
from openerp import models


class PabiPurchaseEmploymentReport(models.Model):
    _name = 'pabi.purchase.employment.report'
    _description = 'Pabi Purchase Employment Report'
    _auto = False

    # purchase_type_id = fields.Many2one(
    #     'purchase.type',
    #     string='Purchase Type',
    # )
    # purchase_method_id = fields.Many2one(
    #     'purchase.method',
    #     string='Purchase Type',
    # )
    # date_from = fields.Date(string='Contract Start Date')
    # date_to = fields.Date(string='Contract End Date')

    def init(self, cr):
        tools.drop_view_if_exists(cr, self._table)
        cr.execute("""CREATE or REPLACE VIEW %s as (
        SELECT
        pp.name_template AS product_name,
        po.name AS po_name,
        pol.product_qty AS qty,
        pol.price_unit AS pr_price,
        (pol.price_unit * pol.product_qty) + (at.amount * (pol.price_unit * pol.product_qty)) AS amount_line,
        pol.date_planned AS planned_date,
        po.date_order AS order_date,
	    pol.name AS description
        FROM
        purchase_order po
        LEFT JOIN purchase_order_line pol on pol.order_id = po.id
        LEFT JOIN purchase_order_taxe pot ON pot.ord_id = po.id
        LEFT JOIN purchase_requisition prq ON po.requisition_id = prq.id
        LEFT JOIN purchase_type pt ON prq.purchase_type_id = pt.id
        LEFT JOIN account_tax at on pot.tax_id = at.id
        LEFT JOIN product_product pp ON pp.id =  pol.product_id
        WHERE po.state != 'cancel'
        AND po.order_type = 'purchase_order'
        AND pt.name = 'จ้าง'
        ORDER BY po.name
        )""" % (self._table, ))
