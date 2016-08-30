# -*- coding: utf-8 -*-
from openerp import models, fields, api, _
from openerp.exceptions import ValidationError


class BudgetFundRule(models.Model):
    _name = "budget.fund.rule"
    _description = "Rule for Budget's Fund vs Project"

    name = fields.Char(
        string='Number',
        index=True,
        required=True,
        default='/',
        copy=False,
    )
    fiscalyear_id = fields.Many2one(
        'account.fiscalyear',
        string='Fiscal Year',
        required=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    planned_amount = fields.Float(
        string='Total Planned Amount',
        compute='_compute_planned_amount',
        readonly=True,
    )
    fund_id = fields.Many2one(
        'res.fund',
        string='Fund',
        required=True,
    )
    project_id = fields.Many2one(
        'res.project',
        string='Project',
        required=True,
    )
    activity_group_spending_rule_ids = fields.One2many(
        'budget.fund.rule.activity.group',
        'fund_rule_id',
        string='Activity Group Spending Rules',
        help="Spending rule for each activity group",
    )
    custom_rule_line_ids = fields.One2many(
        'budget.fund.rule.custom.rule.line',
        'fund_rule_id',
        string='Custom Rules',
    )

    _sql_constraints = [
        ('fund_project_uniq', 'unique(fund_id, project_id)',
            'Fund vs Project must be unique!'),
    ]

    @api.multi
    @api.depends('activity_group_spending_rule_ids')
    def _compute_planned_amount(self):
        for rec in self:
            rec.planned_amount = sum([x.planned_amount for x in
                                      rec.activity_group_spending_rule_ids])

    @api.onchange('fiscalyear_id', 'fund_id', 'project_id')
    def _onchange_create_activity_group_spending_rule(self):
        self.activity_group_spending_rule_ids = False
        self.activity_group_spending_rule_ids = []
        BudgetLine = self.env['account.budget.line']
        budget_lines = BudgetLine.search(
            [('budget_id.fiscalyear_id', '=', self.fiscalyear_id.id),
             ('project_id', '=', self.project_id.id),
             ('fund_id', '=', self.fund_id.id),
             ('activity_group_id', '!=', False)])
        for line in budget_lines:
            new_rule = self.env['budget.fund.rule.activity.group'].new()
            new_rule.activity_group_id = line.activity_group_id
            new_rule.budget_line_ref_id = line
            new_rule.max_spending_percent = 100
            new_rule.is_control = True
            self.activity_group_spending_rule_ids += new_rule

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = \
                self.env['ir.sequence'].get('budget.fund.rule') or '/'
        return super(BudgetFundRule, self).create(vals)

    @api.model
    def document_check_fund_activity_spending(self, fiscalyear_id,
                                              doc_lines, amount_field):
            group_vals = []
            for l in doc_lines:
                val = ()
                for f in ['project_id', 'fund_id', 'activity_group_id']:
                    val += (l[f].id,)
                if False not in val:
                    group_vals.append(val)
            group_vals = list(set(group_vals))
            for val in group_vals:
                project_id, fund_id, activity_group_id = val[0], val[1], val[2]
                filtered_lines = doc_lines
                i = 0
                for f in ['project_id', 'fund_id', 'activity_group_id']:
                    filtered_lines = filtered_lines.\
                        filtered(lambda l:
                                 f in l and l[f] and l[f].id == val[i])
                    i += 1
                amount = sum(filtered_lines.mapped('price_subtotal'))
                self.check_fund_activity_spending(fiscalyear_id,
                                                  project_id,
                                                  fund_id,
                                                  activity_group_id,
                                                  amount)

    @api.model
    def check_fund_activity_spending(self, fiscalyear_id, project_id,
                                     fund_id, activity_group_id, amount):
        rule = self.env['budget.fund.rule.activity.group'].\
            search([('fiscalyear_id', '=', fiscalyear_id),
                    ('project_id', '=', project_id),
                    ('fund_id', '=', fund_id),
                    ('activity_group_id', '=', activity_group_id),
                    ('is_control', '=', True)])
        if not rule:
            return
        max_spending_percent = rule.max_spending_percent
        self._cr.execute("""
            select
                coalesce(sum(planned_amount), 0.0) as planned_amount,
                coalesce(sum(released_amount), 0.0) as released_amount,
                coalesce(sum(amount_balance), 0.0) as amount_balance
            from budget_monitor_report
            where fiscalyear_id = %s
                and project_id = %s
                and fund_id = %s
                and activity_group_id = %s
        """, (fiscalyear_id, project_id, fund_id, activity_group_id,))
        res = self._cr.fetchone()
        released_amount = res[1]
        amount_balance = res[2]
        ActivityGroup = self.env['account.activity.group']
        group = ActivityGroup.browse(activity_group_id)
        if released_amount <= 0.0:
            raise ValidationError(
                _('No budget released for Activity Group %s!') %
                (group.name,))
        spending_percent = 100.0 * ((released_amount -
                                     amount_balance +
                                     amount) /
                                    released_amount)
        if spending_percent > max_spending_percent:
            raise ValidationError(
                _('Amount exceeded maximum spending '
                  'for Activity Group %s!\n'
                  '(%s%% vs %s%%)') %
                (group.name,
                 round(spending_percent, 2),
                 round(max_spending_percent, 2)))


class BudgetFundRuleActivityGroup(models.Model):
    _name = "budget.fund.rule.activity.group"
    _description = "Spending Rule specific for Activity Group"

    fund_rule_id = fields.Many2one(
        'budget.fund.rule',
        string='Funding Rule',
        index=True,
        ondelete='cascade',
    )
    budget_line_ref_id = fields.Many2one(
        'account.budget.line',
        string='Budget Line',
        readonly=True,
    )
    budget_ref_id = fields.Many2one(
        'account.budget',
        string='Budget Control',
        related='budget_line_ref_id.budget_id',
    )
    fiscalyear_id = fields.Many2one(
        'account.fiscalyear',
        related='fund_rule_id.fiscalyear_id',
        string='Fiscal Year',
        store=True,
    )
    project_id = fields.Many2one(
        'res.project',
        related='fund_rule_id.project_id',
        string='Project',
        store=True,
    )
    fund_id = fields.Many2one(
        'res.fund',
        related='fund_rule_id.fund_id',
        string='Fund',
        store=True,
    )
    activity_group_id = fields.Many2one(
        'account.activity.group',
        string='Activity Group',
    )
    planned_amount = fields.Float(
        string='Planned Amount',
        related='budget_line_ref_id.planned_amount',
        readonly=True,
    )
    max_spending_percent = fields.Integer(
        string='Max Spending (%)',
        default=100.0,
    )
    is_control = fields.Boolean(
        string='Control',
        default=True,
    )


class BudgetFundRuleCustomRuleLine(models.Model):
    _name = "budget.fund.rule.custom.rule.line"
    _description = "Fund Rule's Custom Rules"
    _order = "sequence, id"

    sequence = fields.Integer(
        string='Sequence',
        index=True,
        default=1,
    )
    fund_rule_id = fields.Many2one(
        'budget.fund.rule',
        string='Funding Rule',
        index=True,
        ondelete='cascade',
    )
    custom_rule_id = fields.Many2one(
        'budget.custom.rule',
        string='Custom Rule',
        required=True,
    )
    activity_group_ids = fields.Many2many(
        'account.activity.group',
        'budget_custom_rule_activity_group_rel',
        'custom_rule_line_id', 'activity_group_id',
        string='Activity Groups',
    )
    params = fields.Char(
        string='Parameters',
    )
    help = fields.Text(
        string='Help',
    )
    is_control = fields.Boolean(
        string='Control',
        default=True,
    )

    @api.onchange('custom_rule_id')
    def _onchange_custom_rule_id(self):
        self.help = self.custom_rule_id.help


class BudgetCustomRule(models.Model):
    _name = "budget.custom.rule"
    _description = "Budget Custom Rules"

    name = fields.Char(
        string='Name',
        required=True,
    )
    logic = fields.Text(
        string='Logic',
        required=True,
    )
    help = fields.Text(
        string='Help',
        required=True,
    )