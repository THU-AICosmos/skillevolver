Write a performance review letter for one of our employees. Follow the Word template (`performance_review_template.docx`) with placeholders like `{{EMPLOYEE_FULL_NAME}}`, `{{JOB_TITLE}}`, etc.

The required information is in `review_data.json`.

Your task is to fill in the placeholders in the template and save the result to `/root/performance_review_filled.docx`. Also, there's a conditional section marked with `{{IF_BONUS}}...{{END_IF_BONUS}}`. You should keep that content if BONUS_ELIGIBLE is set to Yes but remove the IF/END_IF markers for the final review letter.
