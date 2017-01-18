# -*- coding: utf-8 -*-
from openerp import tools
from openerp import models


class PabiPurchaseGreenProductReport(models.Model):
    _name = 'pabi.purchase.green.product.report'
    _description = 'Pabi Purchase Green Product Report'
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
        prl.product_qty AS qty,
        prl.price_unit AS pr_price,
        (prql.price_unit * prql.product_qty) + (at.amount * (prql.price_unit * prql.product_qty)) AS budget,
        prq.schedule_date AS schedule_date,
        prl.is_green_product AS is_green,
	    prl.product_name AS description
        FROM
        purchase_requisition_line prl
        LEFT JOIN purchase_requisition prq ON prl.requisition_id = prq.id
        LEFT JOIN purchase_request_purchase_requisition_line_rel prprl on prl.id = purchase_requisition_line_id
        LEFT JOIN purchase_request_line prql ON prprl.purchase_request_line_id = prql.id
        LEFT JOIN purchase_order_line pol on pol.requisition_line_id = prl.id
        LEFT JOIN purchase_order po on pol.order_id = po.id
        LEFT JOIN purchase_request_taxes_rel prtl ON prtl.request_line_id = prql.id
        LEFT JOIN account_tax at on prtl.tax_id = at.id
        LEFT JOIN product_product pp ON pp.id =  prl.product_id
        WHERE po.state in ('confirmed','assigned')
        and po.order_type = 'purchase_order'
        ORDER BY prql.name
        )""" % (self._table, ))
