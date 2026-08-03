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

## group-family-applications funnel [INFO]
Sequential funnel over group_started, traveller_added, traveller_removed, group_submitted: {"group_started": 1200, "traveller_added": 1200, "traveller_removed": 57, "group_submitted": 25}

**Metric:** spec_funnel_users  
**Value:** {'group_started': 1200, 'traveller_added': 1200, 'traveller_removed': 57, 'group_submitted': 25}  

## group-family-applications drop-off: group_started -> traveller_added [INFO]
0.0% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 0.0  

## group-family-applications drop-off: traveller_added -> traveller_removed [WARNING]
95.2% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 95.25  

## group-family-applications drop-off: traveller_removed -> group_submitted [WARNING]
56.1% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 56.14035087719298  

## Group application completion rate critically low [CRITICAL]
Only 25 of 1,200 group applications submitted (2.1% completion). Fix group submission funnel.

**Metric:** group_started → group_submitted completion  
**Value:** 2.1%  

## Massive drop-off between traveller_added and group_submitted [CRITICAL]
1,200 travellers added but only 25 groups submitted (97.9% drop-off). Investigate submission UX.

**Metric:** traveller_added → group_submitted drop-off  
**Value:** 97.9%  

## Traveller removal minimal; not a churn driver [INFO]
Only 57 of 1,200 travellers removed (4.75%). Add/remove churn is negligible.

**Metric:** traveller_removed / traveller_added  
**Value:** 4.75%  

## Cannot answer group-size completion rate — no size breakdown in data [WARNING]
Query lacks group_size segmentation. Cannot identify which group sizes convert best.

**Metric:** group_size completion rate  
**Value:** N/A  

## Cannot answer per-traveller document completion bottleneck — no docs_complete data [WARNING]
Query lacks docs_complete metric. Cannot determine if document completion blocks big groups.

**Metric:** docs_complete by group_size  
**Value:** N/A  

## India dominates group applications (60.5% of starts) [INFO]
726 of 1,200 group_started events from India. Verify destination/segment mix.

**Metric:** group_started by geoip_country_code  
**Value:** IN: 60.5%  

## SG and AE show higher group submission rates than India [INFO]
SG: 64/118 submitted (54.2%), AE: 73/121 (60.3%), IN: 419/726 (57.7%). SG/AE more engaged.

**Metric:** group_submitted / group_started by geo  
**Value:** SG 54.2%, AE 60.3%, IN 57.7%  

## iOS leads group application adoption [INFO]
484 of 1,200 group_started from iOS (40.3%). Android 32.9%, web 19.3%.

**Metric:** group_started by device_type  
**Value:** iOS 40.3%  

## Cannot answer destination/segment drivers — no destination data in group tables [WARNING]
Query lacks destination breakdown for group_started/submitted. Cannot identify high-intent destinations.

**Metric:** group_submitted by destination  
**Value:** N/A  

## Group application flow newly instrumented — baseline missing [INFO]
group_started, traveller_added, traveller_removed, group_submitted tables are new. No historical comparison available.

**Metric:** group_application instrumentation  
**Value:** newly_added  

## Thailand leads group applications with perfect submission [INFO]
Thailand drives 112 group starts, all 112 submitted (100% completion). Highest volume destination.

**Metric:** group_applications_started  
**Value:** 112  

## Malaysia and US follow Thailand in group volume [INFO]
Malaysia 103 starts (100% submitted), US 100 starts (100% submitted). Both destinations show perfect completion.

**Metric:** group_applications_started  
**Value:** 103–100  

## All top 14 destinations show 100% group submission rate [INFO]
Every destination in results (TH, MY, US, TR, AE, GB, EG, ID, FR, SG, GR, AU, VN, JP) converts 100% of group starts to submissions.

**Metric:** submission_rate_pct  
**Value:** 100.0  

## iOS dominates group application starts across all destinations [INFO]
iOS accounts for 40–43% of group starts in top destinations (TH 48/112, MY 42/103, US 46/100). Consistent platform preference.

**Metric:** ios_starts_pct  
**Value:** 40–43%  

## Web-user-b2c represents 15–20% of group starts [INFO]
Web users contribute 12–23 starts per destination (TH 23/112, MY 21/103). Meaningful but smaller than mobile.

**Metric:** web_starts_pct  
**Value:** 15–20%  

## Indonesia shows Android parity with iOS [INFO]
Indonesia 36 Android vs 24 iOS starts (60% Android). Only destination where Android leads or matches iOS.

**Metric:** android_starts  
**Value:** 36  

## SEA destinations (TH, MY, ID, SG, VN) drive 416 of 1,200 group starts [INFO]
Southeast Asia accounts for 35% of group application volume. Strongest regional cluster.

**Metric:** group_applications_started  
**Value:** 416  

## No destination-level completion variance detected [WARNING]
Query shows 100% submission rate across all 14 destinations. Cannot identify low-performing destinations to optimize.

**Metric:** submission_rate_pct  
**Value:** 100.0  

## Weekly conversion peaked mid-May, declining into June [WARNING]
322 purchases week-of May 10; dropped 60% to 130 by June 28. Investigate Schengen summer slot scarcity (K4) impact.

**Metric:** weekly_purchases  
**Value:** 322 → 130 (−60%)  

## Conversion volatility high; no clear weekly pattern [INFO]
Weekly purchases range 130–322 (2.5x spread) over 90 days. Stabilize measurement or segment by destination/cohort.

**Metric:** weekly_purchase_variance  
**Value:** 130–322 purchases/week  

## Latest week (Jun 28) shows sharp 54% drop [CRITICAL]
130 purchases vs 283 prior week. Confirm data freshness; check for app version rollout (K7) or campaign end (K6).

**Metric:** week_over_week_change  
**Value:** −54% (283 → 130)  

