# Analytics Insights

## Conversion Funnel Overview [INFO]
Funnel metrics: {"destination_card_clicked": 1000000, "application_started": 154413, "document_uploaded": 19523, "purchase_completed": 3366}

**Metric:** funnel_users  
**Value:** {'destination_card_clicked': 1000000, 'application_started': 154413, 'document_uploaded': 19523, 'purchase_completed': 3366}  

## Drop-off: destination_card_clicked -> application_started [WARNING]
84.6% of users drop off at this step

**Metric:** drop_off_rate  
**Value:** 84.5587  

## Drop-off: application_started -> document_uploaded [WARNING]
87.4% of users drop off at this step

**Metric:** drop_off_rate  
**Value:** 87.35663448025748  

## Drop-off: document_uploaded -> purchase_completed [WARNING]
82.8% of users drop off at this step

**Metric:** drop_off_rate  
**Value:** 82.75879731598627  

## Top device_type for destination_card_clicked [INFO]
ios: 420838 users

**Metric:** top_device_type  
**Value:** {'device_type': 'ios', 'users': 420838, 'events': 420838}  

## Top geoip_country_code for destination_card_clicked [INFO]
IN: 559795 users

**Metric:** top_geoip_country_code  
**Value:** {'geoip_country_code': 'IN', 'users': 559795, 'events': 559795}  

## Top funnel_type for destination_card_clicked [INFO]
b2c: 859648 users

**Metric:** top_funnel_type  
**Value:** {'funnel_type': 'b2c', 'users': 859648, 'events': 859648}  

## Top device_type for application_started [INFO]
ios: 63520 users

**Metric:** top_device_type  
**Value:** {'device_type': 'ios', 'users': 63520, 'events': 63520}  

## Top geoip_country_code for application_started [INFO]
IN: 86506 users

**Metric:** top_geoip_country_code  
**Value:** {'geoip_country_code': 'IN', 'users': 86506, 'events': 86506}  

## Top funnel_type for application_started [INFO]
b2c: 132776 users

**Metric:** top_funnel_type  
**Value:** {'funnel_type': 'b2c', 'users': 132776, 'events': 132776}  

## Top device_type for purchase_completed [INFO]
ios: 3193 users

**Metric:** top_device_type  
**Value:** {'device_type': 'ios', 'users': 3193, 'events': 3193}  

## Top geoip_country_code for purchase_completed [INFO]
IN: 3791 users

**Metric:** top_geoip_country_code  
**Value:** {'geoip_country_code': 'IN', 'users': 3791, 'events': 3791}  

## Top funnel_type for purchase_completed [INFO]
b2c: 6098 users

**Metric:** top_funnel_type  
**Value:** {'funnel_type': 'b2c', 'users': 6098, 'events': 6098}  

## express-checkout funnel [INFO]
Sequential funnel over express_checkout_shown, express_checkout_selected, saved_method_used, otp_entered, express_payment_confirmed: {"express_checkout_shown": 1650, "express_checkout_selected": 1007, "saved_method_used": 1007, "otp_entered": 1007, "express_payment_confirmed": 836}

**Metric:** spec_funnel_users  
**Value:** {'express_checkout_shown': 1650, 'express_checkout_selected': 1007, 'saved_method_used': 1007, 'otp_entered': 1007, 'express_payment_confirmed': 836}  

## express-checkout drop-off: express_checkout_shown -> express_checkout_selected [INFO]
39.0% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 38.96969696969697  

## express-checkout drop-off: express_checkout_selected -> saved_method_used [INFO]
0.0% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 0.0  

## express-checkout drop-off: saved_method_used -> otp_entered [INFO]
0.0% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 0.0  

## express-checkout drop-off: otp_entered -> express_payment_confirmed [INFO]
17.0% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 16.9811320754717  

## Express payment confirmation now 83% — critical recovery from K1 [INFO]
836 of 1,007 OTP users confirmed payment (83% vs 0% in K1). Express checkout funnel restored; K1 issue resolved.

**Metric:** otp_entered → express_payment_confirmed  
**Value:** 83.0%  

## Express adoption 61% — 39% abandon at selection step [WARNING]
1,007 of 1,650 shown Express selected it (61% adoption). 643 users drop before payment entry.

**Metric:** express_checkout_selected / express_checkout_shown  
**Value:** 61.0%  

## iOS 74% OTP success vs Android 90% — iOS underperforms [WARNING]
iOS: 316/428 confirmed (74%). Android: 303/338 confirmed (90%). iOS OTP conversion 16 points lower.

**Metric:** otp_success_rate by device  
**Value:** iOS 74% vs Android 90%  

## India 84% Express selection but SG/AE show 64%/57% — geo intent gap [INFO]
IN: 606/1,007 selected (60% of pool, 60% selection). SG: 94/147 (64% selection). AE: 88/153 (57%). India underconverts vs intent.

**Metric:** express_checkout_selected by geo  
**Value:** IN 60% vs SG 64% vs AE 57%  

## Cannot measure Express vs standard checkout lift — no baseline [WARNING]
Query lacks standard checkout funnel. Cannot compute conversion lift or answer spec Q1.

**Metric:** standard_checkout funnel  
**Value:** N/A  

## Cannot measure Express payment latency — no timing data [WARNING]
Query lacks payment.latency_ms or time-to-confirmation. Cannot answer spec Q3 (speed comparison).

**Metric:** payment.latency_ms  
**Value:** N/A  

## Web-user-b2c 92% OTP success — highest platform confidence [INFO]
Web: 170/185 confirmed (92% success). Desktop: 47/56 (84%). Mobile lags web by 8–18 points.

**Metric:** otp_success_rate by device  
**Value:** Web 92% vs iOS 74% vs Android 90%  

## SG Express users 64% selection rate — highest geo intent [INFO]
SG: 94/147 selected (64%). Outperforms IN (60%), AE (57%), US (62%). SG most ready for Express.

**Metric:** express_checkout_selected / express_checkout_shown by geo  
**Value:** SG 64%  

