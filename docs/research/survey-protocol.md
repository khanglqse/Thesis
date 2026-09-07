# Traffic observation and quality-control protocol

This protocol applies if continuous video or movement counts become available. It also defines how published aggregate counts are represented.

## Observation unit

The atomic row is a 15-minute interval for one approach, movement (`left`, `through`, `right`) and vehicle class (`motorcycle`, `car`, `bus`, `truck`, `bicycle`, `other`). Preserve the original timestamp and timezone. Five-minute rows may be retained when source video permits later aggregation. Missing, occluded and unavailable are explicit states; none is encoded as zero.

Required metadata: source ID, site ID and coordinates; collection date/time/timezone; camera ID and viewpoint; weather/event note; approach/movement mapping; raw or estimated status; unit (`vehicle`, `PCU`, or rate); PCU factors and their source; signal-plan ID valid at that time; counter/tool version; reviewer; license/access conditions.

## Quality control

- Independently count 20% of intervals, stratified across normal, AM peak, PM peak, movements and vehicle classes.
- Report absolute count difference, relative difference where the denominator is nonzero, and total/class/movement agreement. Resolve systematic mapping errors before averaging counters.
- If one counter is available, perform a blind recount after at least one day and label the limitation.
- Keep raw class counts separate from PCU conversion. Detection mAP is not count accuracy.
- Record occlusion, stopped vehicles crossing a line more than once, U-turns, filtering motorcycles and camera interruptions.
- For published tables with estimated directions, store `observation_status=estimated_from_published_ratio` at the movement level.

## Split policy

Group splits by day/session, never by randomly splitting rows from one continuous video. Calibration uses train days; simulator and controller selection use validation days; the final test days remain sealed until the protocol and candidates are frozen. If only one published peak aggregate exists, it is a calibration/face-validity case and cannot estimate day-to-day generalization.

## Handoff format

The normalized CSV/JSON schema is: `source_id, site_id, timestamp_start, interval_s, approach_id, movement, vehicle_class, raw_count, pcu_factor, pcu_count, observation_status, quality_flag, split_group`. Mapping files relate approach/movement to SUMO edges and signal links. All derived demand files store a hash of the normalized observations and transformation config.
