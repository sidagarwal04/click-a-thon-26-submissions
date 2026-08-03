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

## abandoned-checkout-recovery funnel [INFO]
Sequential funnel over abandonment_detected, reminder_sent, reminder_opened, reminder_cta_clicked, resumed_at_step, reconverted: {"abandonment_detected": 2300, "reminder_sent": 2300, "reminder_opened": 351, "reminder_cta_clicked": 49, "resumed_at_step": 16, "reconverted": 1}

**Metric:** spec_funnel_users  
**Value:** {'abandonment_detected': 2300, 'reminder_sent': 2300, 'reminder_opened': 351, 'reminder_cta_clicked': 49, 'resumed_at_step': 16, 'reconverted': 1}  

## abandoned-checkout-recovery drop-off: abandonment_detected -> reminder_sent [INFO]
0.0% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 0.0  

## abandoned-checkout-recovery drop-off: reminder_sent -> reminder_opened [WARNING]
84.7% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 84.73913043478261  

## abandoned-checkout-recovery drop-off: reminder_opened -> reminder_cta_clicked [WARNING]
86.0% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 86.03988603988604  

## abandoned-checkout-recovery drop-off: reminder_cta_clicked -> resumed_at_step [WARNING]
67.3% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 67.3469387755102  

## abandoned-checkout-recovery drop-off: resumed_at_step -> reconverted [WARNING]
93.8% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 93.75  

## Recovery funnel exists but severely leaky [CRITICAL]
2,300 abandoned users detected; only 1 reconverted (0.04% recovery rate). Reminder open rate 15.3% is the bottleneck.

**Metric:** reconversion_rate  
**Value:** 0.04%  

## Reminder engagement collapses post-open [CRITICAL]
351 reminders opened but only 49 CTAs clicked (14% CTA rate). Message content or CTA placement failing.

**Metric:** reminder_cta_click_rate  
**Value:** 14%  

## Resume-to-reconvert conversion near zero [CRITICAL]
16 users resumed at drop step; only 1 completed purchase (6.25% conversion). Recovery targeting or funnel friction post-resume.

**Metric:** resumed_to_reconvert_rate  
**Value:** 6.25%  

## iOS dominates recovery funnel but underconverts [WARNING]
313 iOS reminders opened (89% of opens) but only 42 iOS reconversions (13.4% of total). iOS-specific friction post-reminder.

**Metric:** ios_reconversion_rate  
**Value:** 13.4%  

## India drives recovery volume but low conversion [WARNING]
1,390 Indian abandons detected (60% of total); 63 reconversions (4.5% recovery). Geo-specific messaging or payment friction.

**Metric:** india_recovery_rate  
**Value:** 4.5%  

## No drop_step or channel breakdown in recovery data [WARNING]
Cannot determine which funnel step is most recoverable or which channel (push/email/WhatsApp) recovers best. Query missing drop_step and channel columns.

**Metric:** data_completeness  
**Value:** incomplete  

## No timing analysis (hours_since_drop) available [WARNING]
Cannot compare 1h vs 24h vs 48h reminder send timing. Query missing hours_since_drop column required to answer spec question.

**Metric:** data_completeness  
**Value:** incomplete  

## Core funnel drop-off exceeds 82% at every step [CRITICAL]
84.6% drop card→app, 87.4% drop app→doc, 82.8% drop doc→purchase. Recovery funnel cannot offset core funnel leakage.

**Metric:** core_funnel_drop_rate  
**Value:** 82-87%  

## Recovery funnel volume negligible vs core funnel [INFO]
2,300 abandonments detected vs 3,366 total purchases. Recovery captures <0.1% of core conversion volume.

**Metric:** recovery_volume_ratio  
**Value:** <0.1%  

