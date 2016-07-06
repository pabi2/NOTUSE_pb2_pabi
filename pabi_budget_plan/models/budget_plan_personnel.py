# -*- coding: utf-8 -*-
from openerp import models, fields, api
from .budget_plan_template import BudgetPlanCommon


class BudgetPlanPersonnel(BudgetPlanCommon, models.Model):
    _name = 'budget.plan.personnel'
    _inherits = {'budget.plan.template': 'template_id'}
    _description = "Personnel Budget - Budget Plan"

    template_id = fields.Many2one(
        'budget.plan.template',
        required=True,
        ondelete='cascade',
    )
    plan_line_ids = fields.One2many(
        'budget.plan.personnel.line',
        'plan_id',
        string='Budget Plan Lines',
        copy=False,
    )
    planned_overall = fields.Float(
        string='Budget Plan',
        compute='_compute_planned_overall',
        store=True,
    )

    @api.onchange('personnel_costcenter_id')
    def _onchange_personnel_costcenter_id(self):
        self.section_id = self.personnel_costcenter_id.section_id

    # Call inherited methods
    @api.multi
    def unlink(self):
        for rec in self:
            rec.plan_line_ids.mapped('template_id').unlink()
        self.mapped('template_id').unlink()
        return super(BudgetPlanPersonnel, self).unlink()

    @api.model
    def convert_plan_to_budget_control(self, active_ids):
        head_src_model = self.env['budget.plan.personnel']
        line_src_model = self.env['budget.plan.personnel.line']

        self._convert_plan_to_budget_control(active_ids,
                                             head_src_model,
                                             line_src_model)


class BudgetPlanPersonnelLine(models.Model):
    _name = 'budget.plan.personnel.line'
    _inherits = {'budget.plan.line.template': 'template_id'}
    _description = "Personnel Budget - Budget Plan Line"

    plan_id = fields.Many2one(
        'budget.plan.personnel',
        string='Budget Plan',
        ondelete='cascade',
        index=True,
        required=True,
    )
    template_id = fields.Many2one(
        'budget.plan.line.template',
        required=True,
        ondelete='cascade',
    )
    activity_group_id = fields.Many2one(
        'account.activity.group',
        string='Activity Group',
    )
    activity_id = fields.Many2one(
        'account.activity',
        string='Activity',
    )

    @api.model
    def create(self, vals):
        res = super(BudgetPlanPersonnelLine, self).create(vals)
        res.write({'chart_view': res.plan_id.chart_view,
                   'fiscalyear_id': res.plan_id.fiscalyear_id.id})
        return res

    @api.multi
    def unlink(self):
        self.mapped('template_id').unlink()
        return super(BudgetPlanPersonnelLine, self).unlink()