# Sample Knowledge Base for PDF Filling

## PDF Form Field Standards

This knowledge base provides guidelines for filling common PDF form fields:

### Personal Information Fields
- **Name**: Text field for full name (e.g., "John Doe")
- **First Name**: Text field for first name only
- **Last Name**: Text field for last name only
- **SSN**: Social Security Number (format: XXX-XX-XXXX)
- **DOB**: Date of Birth (format: MM/DD/YYYY)
- **Email**: Email address
- **Phone**: Phone number (format: XXX-XXX-XXXX)

### Address Fields
- **Street Address**: Street address line 1
- **City**: City name
- **State**: Two-letter state abbreviation (e.g., "CA")
- **ZIP Code**: 5-digit ZIP code
- **Country**: Country name

### Employment Fields
- **Job Title**: Current job title
- **Employer**: Company name
- **Years Employed**: Number of years at current job
- **Annual Income**: Annual salary/income amount

### Financial Fields
- **Account Number**: Bank account number
- **Routing Number**: Bank routing number
- **Credit Card Number**: Credit card number (format: XXXX-XXXX-XXXX-XXXX)
- **Expiration Date**: Credit card expiration (format: MM/YY)

## Field Value Guidelines

1. **Text Fields**: Use string values, trim whitespace
2. **Numeric Fields**: Convert to appropriate numeric type if needed
3. **Date Fields**: Use MM/DD/YYYY format unless specified otherwise
4. **Phone Numbers**: Use XXX-XXX-XXXX format
5. **SSN**: Use XXX-XX-XXXX format
6. **ZIP Codes**: Use 5-digit format (XXXXX)

## Code Generation Rules

1. Always import fitz (PyMuPDF) at the top
2. Open PDF with fitz.open(pdf_path)
3. Iterate through all pages and widgets
4. Match field names case-insensitively when possible
5. Set field_value and call widget.update()
6. Save with doc.save(output_path, incremental=False)
7. Always close the document with doc.close()

## Error Handling

- Check if PDF file exists before processing
- Validate field names exist in the PDF
- Handle cases where fields are read-only
- Provide meaningful error messages for debugging
- Log field mapping decisions for transparency
