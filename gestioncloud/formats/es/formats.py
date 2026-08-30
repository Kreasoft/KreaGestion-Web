# Formato de fechas y números para español
THOUSAND_SEPARATOR = '.'
DECIMAL_SEPARATOR = ','
USE_THOUSAND_SEPARATOR = True
NUMBER_GROUPING = 3

DATE_FORMAT = 'd-m-Y'
DATETIME_FORMAT = 'd-m-Y H:i'
SHORT_DATE_FORMAT = 'd-m-Y'
SHORT_DATETIME_FORMAT = 'd-m-Y H:i'
YEAR_MONTH_FORMAT = 'F Y'
MONTH_DAY_FORMAT = 'j \\d\\e F'
TIME_FORMAT = 'H:i'

DATE_INPUT_FORMATS = [
    '%d-%m-%Y',
    '%d/%m/%Y',
    '%Y-%m-%d',
]
DATETIME_INPUT_FORMATS = [
    '%d-%m-%Y %H:%M',
    '%d-%m-%Y %H:%M:%S',
    '%d/%m/%Y %H:%M',
    '%d/%m/%Y %H:%M:%S',
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d %H:%M',
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%dT%H:%M',
]
