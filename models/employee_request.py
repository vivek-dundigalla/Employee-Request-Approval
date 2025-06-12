# models.py
from odoo import models, fields, api, _
from string import Template
from datetime import datetime
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class EmployeeRequest(models.Model):
    _name = 'employee.request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Employee Request'
    _rec_name = 'employee_id'

    name = fields.Char(string="Request Name", default='New')
    req_title = fields.Char(string="Request Title", required=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, tracking=True)
    email = fields.Char(related='employee_id.work_email', string="Employee Email", readonly=False)
    request_type_id = fields.Many2one('request.letter', string="Request Type", tracking=True)

    REQUEST_TYPE_SELECTION = [
        ('experience_certificate', 'Experience Certificate'),
        ('leave_request', 'Leave Request'),
        ('relieving_letter', 'Relieving Letter'),
    ]

    request_type = fields.Selection(
        selection=REQUEST_TYPE_SELECTION,
        string="Request Type Selection",
        required=True,
        tracking=True,
    )

    description = fields.Char(string="Reason/Description")
    date_request = fields.Date(string="Request Date", default=fields.Date.context_today, tracking=True)
    state = fields.Selection([
        ('draft', 'Pending'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], default='draft', string="Status", tracking=True)
    approved_by = fields.Many2one('res.users', string="Approved By", tracking=True)
    approved_date = fields.Datetime(string="Approved Date", tracking=True)
    role = fields.Char(related='employee_id.job_id.name', string="Employee Role", readonly=False)

    rendered_letter = fields.Html(string="Rendered Letter", compute="_compute_rendered_letter", store=False)

    date = fields.Date(string="Date", default=fields.Date.context_today, tracking=True)

    joining_date = fields.Date(string="Joining Date", compute="_compute_joining_date")

    reason = fields.Char(string="Reason")

    total_experience = fields.Char(string="Total Experience", compute="_compute_total_experience")

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")

    resignation_date = fields.Date(string="Resignation Date")
    last_working_day = fields.Date(string="Last Working Day", compute="_compute_last_working_day")

    def _compute_joining_date(self):
        for rec in self:
            resume_lines = self.env['hr.resume.line'].search(
                [('employee_id', '=', rec.employee_id.id), ('date_start', '!=', False)],
                order='date_start asc', limit=1
            )
            rec.joining_date = resume_lines.date_start if resume_lines else None

    @api.onchange('resignation_date')
    def _compute_last_working_day(self):
        notice_period_days = 30  # Example: 30 days notice
        for rec in self:
            if rec.resignation_date:
                rec.last_working_day = rec.resignation_date + relativedelta(days=notice_period_days)

    def _get_experience_details(self, employee):
        from dateutil.relativedelta import relativedelta

        experience_lines = []
        total_months = 0

        resume_lines = self.env['hr.resume.line'].search(
            [('employee_id', '=', employee.id), ('date_start', '!=', False)])

        for line in resume_lines:
            start_date = line.date_start
            end_date = line.date_end or fields.Date.today()

            delta = relativedelta(end_date, start_date)
            months = delta.years * 12 + delta.months
            total_months += months

            experience_lines.append(
                f"{line.name} - {line.line_type_id.name or ''} ({start_date} to {end_date})"
            )

        total_years = total_months // 12
        remaining_months = total_months % 12
        total_exp_str = f"{total_years} Years {remaining_months} Months"

        return experience_lines, total_exp_str

    @api.depends('employee_id')
    def _compute_total_experience(self):
        for rec in self:
            _, total_exp_str = rec._get_experience_details(rec.employee_id)
            rec.total_experience = total_exp_str

    @api.depends('employee_id', 'employee_id.name', 'employee_id.job_id.name',
                 'request_type_id.reason', 'req_title', 'description', 'date_request')
    def _compute_rendered_letter(self):
        for rec in self:
            if rec.request_type_id and rec.request_type_id.reason:
                try:
                    experience_lines, total_exp = rec._get_experience_details(rec.employee_id)
                    experience_html = "<ul>"
                    for exp in experience_lines:
                        experience_html += f"<li>{exp}</li>"
                    experience_html += "</ul>"

                    template = Template(rec.request_type_id.reason or "")
                    rec.rendered_letter = template.safe_substitute({
                        'experience_details': experience_html,
                        'total_experience': total_exp,
                        'name': rec.name or '',
                        'reason': rec.reason or '',
                        'employee_name': rec.employee_id.name or '',
                        'employee_email': rec.email or '',
                        'employee_role': rec.role or '',
                        'request_title': rec.req_title or '',
                        'request_type': rec.request_type_id.name or '',
                        'description': rec.description or '',
                        'request_date': rec.date_request.strftime('%Y-%m-%d') if rec.date_request else '',
                        'request_state': dict(rec._fields['state'].selection).get(rec.state, ''),
                        'approved_by': rec.approved_by.name if rec.approved_by else '',
                        'approved_date': rec.approved_date.strftime('%Y-%m-%d %H:%M:%S') if rec.approved_date else ''
                    })
                except Exception as e:
                    rec.rendered_letter = f"<p>Error rendering template: {e}</p>"
            else:
                rec.rendered_letter = ""

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('employee.request') or 'New'
        return super().create(vals)

    def action_submit(self):
        for rec in self:
            rec.state = 'submitted'
            rec.message_post(body="Request submitted by %s." % rec.employee_id.name)

    def action_approve(self):
        for rec in self:
            rec.state = 'approved'
            rec.approved_by = self.env.user
            rec.approved_date = fields.Datetime.now()
            rec.message_post(body=_("Request approved by %s.") % self.env.user.name)

    def action_reject(self):
        for rec in self:
            rec.state = 'rejected'
            rec.message_post(body=_("Request rejected by %s.") % self.env.user.name)

    def action_print_report(self):
        self.ensure_one()
        if self.request_type == 'experience_certificate':
            return self.env.ref('sdm_employee_request_approval.report_experience_certificate').report_action(self)
        elif self.request_type == 'leave_request':
            return self.env.ref('sdm_employee_request_approval.report_leave_request').report_action(self)
        elif self.request_type == 'relieving_letter':
            return self.env.ref('sdm_employee_request_approval.report_relieving_letter').report_action(self)


    def action_print_report_response(self):
        self.ensure_one()
        if self.request_type == 'experience_certificate':
            return self.env.ref('sdm_employee_request_approval.report_experience_certificate_response').report_action(self)
        elif self.request_type == 'leave_request':
            if self.state == 'rejected':
                return self.env.ref('sdm_employee_request_approval.report_leave_request_rejection').report_action(self)
            else:
                return self.env.ref('sdm_employee_request_approval.report_Leave_request_response').report_action(self)
        elif self.request_type == 'relieving_letter':
            return self.env.ref('sdm_employee_request_approval.report_relieving_letter_response').report_action(self)



class RequestLetter(models.Model):
    _name = 'request.letter'
    _description = 'Request Letter'

    name = fields.Char(string="Letter Name", required=True)
    reason = fields.Html(string="Letter Content (Template)")  # Use HTML for rich formatting
