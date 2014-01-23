from Acquisition import aq_inner
from OFS.SimpleItem import SimpleItem
from zope.component import adapts
from zope.component.interfaces import ComponentLookupError
from zope.interface import Interface, implements
from zope.formlib import form
from zope import schema

import string
from email import Encoders
from email.MIMEBase import MIMEBase
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText

from plone.app.contentrules.browser.formhelper import AddForm, EditForm 
from plone.contentrules.rule.interfaces import IRuleElementData, IExecutable

from Products.CMFCore.utils import getToolByName
from Products.CMFPlone import PloneMessageFactory as _
from Products.CMFPlone.utils import safe_unicode


class IMailAction(Interface):
    """Definition of the configuration available for a mail action
    """
    source = schema.TextLine(title=_(u"Email source"),
                             description=_("The email address that sends the \
email. If no email is provided here, it will use the address of the \
report owner."),
                             required=False)
    recipients = schema.TextLine(title=_(u"Email recipients"),
                                description=_("The email where you want to \
send this message. To send it to different email addresses, just separate them\
 with , By default email will be sent to addresses in the distribution\
 list of the mission report"),
                                required=False)

class MailAction(SimpleItem):
    """
    The implementation of the action defined before
    """
    implements(IMailAction, IRuleElementData)

    subject = u''
    source = u''
    recipients = u''
    message = u''

    element = 'plone.actions.Mail'

    @property
    def summary(self):
        return _(u"Email report to ${recipients}",
                 mapping=dict(recipients=self.recipients))


class MailActionExecutor(object):
    """The executor for this action.
    """
    implements(IExecutable)
    adapts(Interface, IMailAction, Interface)

    def __init__(self, context, element, event):
        self.context = context
        self.element = element
        self.event = event

    def __call__(self):
        recipients = [str(mail.strip()) for mail in \
                      self.element.recipients.split(',')]
        mailhost = getToolByName(aq_inner(self.context), "MailHost")
        if not mailhost:
            raise ComponentLookupError, 'You must have a Mailhost utility to \
execute this action'

        source = self.element.source
        urltool = getToolByName(aq_inner(self.context), "portal_url")
        membertool = getToolByName(aq_inner(self.context),"portal_membership")
        #authortool = getToolByName(aq_inner(self.context),"getMemberInfo")
        portal = urltool.getPortalObject()
        if not source:
            # no source provided, looking for the site wide from email
            # address
            from_address = portal.getProperty('email_from_address')
            if not from_address:
                raise ValueError, 'You must provide a source address for this \
action or enter an email in the portal properties'
            from_name = portal.getProperty('email_from_name')
            source = "%s <%s>" % (from_name, from_address)

        obj = self.event.object
        event_title = safe_unicode(u'Mission Report: ' +
                safe_unicode(obj.Title()))
        event_url = safe_unicode(obj.absolute_url())
        subject = event_title

        #Get email address of author

        creator = obj.Creator()
        member = membertool.getMemberById(creator)
        author = member.getProperty('email')
        authorinfo = membertool.getMemberInfo(creator)
        fullname = authorinfo['fullname']

        msg  = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = author

        #Email html body here

        authors = obj.getAuthors()
        members     = obj.getMembers()
        objective   = safe_unicode(obj.Description())
        ilo_office  = obj.getOffice()
        period_start = safe_unicode(obj.startDate)
        period_end   = safe_unicode(obj.endDate)
        city        = safe_unicode(obj.getCity())
        mission_location = safe_unicode(obj.getMission_location())
        mission_location_other = safe_unicode(obj.getMission_location_other())
        theme = safe_unicode(obj.getTheme())
        theme_other = safe_unicode(obj.getTheme_other())
        SummaryAchievements = safe_unicode(obj.getSummaryAchievements())
        MissionFindings = safe_unicode(obj.getMissionFindings())
        Followup = safe_unicode(obj.getFollowup())
        contacts = safe_unicode(obj.getContacts())
        outcome = safe_unicode(obj.getOutcome())
        outcome_text = safe_unicode(obj.getOutcome_text())
        distribution = safe_unicode(obj.getDistribution())

        delimiter = u','.encode('utf-8')
        br = u'<br />'.encode('utf-8')


        #make values in tuples as unicode and utf-8 safe lists

        members_safe = [ safe_unicode(a) for a in members ]
        ilo_office_safe = [ safe_unicode(a) for a in ilo_office ]
        authors_safe = [ safe_unicode(a) for a in authors ]
        
        email_form = u'''
                <h3>Author(s)</h3>
                $authors
        <h3>Mission Member(s)</h3>
        $members
        <h3>Overall Objective</h3>
        $objective
        <h3>ILO Office</h3>
        $ilo_office
        <h3>Period Covered</h3>
        <b>Start Date:</b> $period_start <br />
        <b>End Date:</b> $period_end <br />
        <h3>City</h3>
        $city
        <h3>Mission Location(s)</h3>
        $mission_location
        <br />
        Other: $mission_location_other
        <h3>ILO Themes</h3>
        $theme
        <br />
        Other: $theme_other
        <h3>Summary of Main Achievements</h3>
        $SummaryAchievements
        <h3>Mission Findings</h3>
        $MissionFindings
        <h3>Follow-up actions/next steps</h3>
        $followup
        <h3>List of Contacts</h3>
        $contacts
        <h3>Outcome</h3>
        $outcome

        $outcome_text

        <h3>Distribution List</h3>
        $distribution
        <p>
        -- <br />
        This report is available online for ILO Staff at: <br />
        <a href="$event_url">$event_url</a>
        '''

        email_template = string.Template(email_form)

        body = email_template.substitute({
            'objective'     : objective,
            'authors'       : br.join(authors_safe),
            'members'       : br.join(members_safe),
            'ilo_office'    : br.join(ilo_office_safe),
            'period_start'  : safe_unicode(period_start),
            'period_end'     : safe_unicode(period_end),
            'city'      : safe_unicode(city),
            'mission_location' :
            safe_unicode(delimiter.join(mission_location)),
            'mission_location_other' : mission_location_other,
            'theme' : safe_unicode(delimiter.join(theme)),
            'theme_other': theme_other,
            'SummaryAchievements' : safe_unicode(SummaryAchievements),
            'MissionFindings' : safe_unicode(MissionFindings),
            'followup' : safe_unicode(Followup),
            'contacts' : safe_unicode(contacts),
            'distribution' : safe_unicode(delimiter.join(distribution)),
            'event_url' : event_url,
            'outcome' : outcome,
            'outcome_text' : outcome_text,
             })

        body_safe = body.encode('utf-8')
        htmlPart = MIMEText(body_safe, 'html', 'utf-8')
        msg.attach(htmlPart)

        #File attachments here should be rewritten into function

        if str(obj.getAttachment1()):

            file = str(obj.getAttachment1())
            ctype = obj.attachment1.getContentType()
            filename = obj.attachment1.filename

            maintype, subtype = ctype.split(('/'), 1)

            attachment = MIMEBase(maintype, subtype)
            attachment.set_payload(file)
            Encoders.encode_base64(attachment)

            attachment.add_header('Content-Disposition', 'attachment',
                    filename = filename)

            msg.attach(attachment)

        if str(obj.getAttachment2()):

            file = str(obj.getAttachment2())
            ctype = obj.attachment2.getContentType()
            filename = obj.attachment2.filename

            maintype, subtype = ctype.split(('/'),1)

            attachment = MIMEBase(maintype, subtype)
            attachment.set_payload(file)
            Encoders.encode_base64(attachment)

            attachment.add_header('Content-Disposition', 'attachment',
                    filename = filename)

            msg.attach(attachment)

        if str(obj.getAttachment3()):

            file = str(obj.getAttachment3())
            ctype = obj.attachment3.getContentType()
            filename = obj.attachment3.filename

            maintype, subtype = ctype.split(('/'), 1)

            attachment = MIMEBase(maintype, subtype)
            attachment.set_payload(file)
            Encoders.encode_base64(attachment)

            attachment.add_header('Content-Disposition', 'attachment',
                    filename = filename)

            msg.attach(attachment)

        if str(obj.getAttachment4()):

            file = str(obj.getAttachment4())
            ctype = obj.attachment4.getContentType()
            filename = obj.attachment4.filename

            maintype, subtype = ctype.split(('/'), 1)

            attachment = MIMEBase(maintype, subtype)
            attachment.set_payload(file)
            Encoders.encode_base64(attachment)

            attachment.add_header('Content-Disposition', 'attachment',
                    filename = filename)

            msg.attach(attachment)

        if str(obj.getAttachment5()):

            file = str(obj.getAttachment5())
            ctype = obj.attachment5.getContentType()
            filename = obj.attachment5.filename

            maintype, subtype = ctype.split(('/'), 1)

            attachment = MIMEBase(maintype, subtype)
            attachment.set_payload(file)
            Encoders.encode_base64(attachment)

            attachment.add_header('Content-Disposition', 'attachment',
                    filename = filename)

            msg.attach(attachment)

        #FIXME distribution needs error checking

        for recipient in distribution:
            #Delete previous To headers in loop as default behaviour is
            #append

            del msg['To']
            msg['To'] = recipient

            mailhost.send(msg.as_string())

        return True



class MailAddForm(AddForm):
    """
    An add form for the mail action
    """
    form_fields = form.FormFields(IMailAction)
    label = _(u"Add Mail Action")
    description = _(u"A mail action can mail different recipient.")
    form_name = _(u"Configure element")

    def create(self, data):
        a = MailAction()
        form.applyChanges(a, self.form_fields, data)
        return a

class MailEditForm(EditForm):
    """
    An edit form for the mail action
    """
    form_fields = form.FormFields(IMailAction)
    label = _(u"Edit Mail Action")
    description = _(u"A mail action can mail different recipient.")
    form_name = _(u"Configure element")
