You need to read consultation booking request emails from `/root/test_input.json` file and send a confirmation reply with your proposed consultation time. You may check the folder `/root/auth/gmail/` and `/root/auth/calendar/` for authentication when accessing your calendar and sending emails.

## Workflow
1. Extract key details from consultation booking request emails, such as preferred dates, time windows, and session duration
2. Check your calendar to find a compatible open time slot, and select the earliest available slot if multiple options exist
3. Send the reply email to the `from_email` address using this template:
    """Hello,

        Thanks for reaching out to book a consultation.

        Here is the proposed slot:

        Scheduled Date: {day_name}, {date_formatted}
        Scheduled Time: {time_range}
        Session Length: {sessionDuration} hour(s)

        Please reply if you need to reschedule or have any questions.

        Kind regards,
        SkillsBench Scheduler"""

   - The date format should be `{day_name}, {month} {DD}, {YYYY}`. For example: `Wednesday, February 11, 2026` (NOT `February 11th, 2026` or `February 11, 2026` without day name)
   - The time format should be `{HH:MM AM/PM} - {HH:MM AM/PM}`. For example: `02:00 PM - 03:00 PM` (NOT `2:00 PM - 3:00 PM`)
4. Save the messageID of the emails you sent in `/root/results.json` using the format:
{"sent_results": [{"messageId": <messageID of first email you sent>}, {"messageId": <messageID of second email you sent>}, ....]}
