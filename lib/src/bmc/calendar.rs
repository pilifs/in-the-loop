//! Calendar operations after a JVM observation qualified the default and explicit
//! UTC factories. A factory initializes its calendar to the current time. Conversion
//! reads only complete, canonical civil fields set since creation, after the standard
//! Gregorian cutover, with AD as observed at startup. No timestamp is read from the host.

use super::*;

const CALENDAR: &str = "java/util/GregorianCalendar";
const ZONE: &str = "sun/util/calendar/ZoneInfo";
const DATE: &str = "java/util/Date";
const MARK: &str = "<observed UTC calendar>";
const EXPLICIT_ZONE: &str = "<JDK.tzdb.UTC>";
const FIELDS: [&str; 7] = ["<year>", "<month>", "<day>", "<hour>", "<minute>", "<second>", "<millisecond>"];
const ASSUMPTION: &str = "Calendar factories use the observed JDK's fresh lenient AD Gregorian calendars in fixed UTC, with the standard Gregorian cutover and the default locale and time zone seen at startup";

/// March-based Gregorian years place the leap day at the end of the year.
/// 719468 is the March-based day number of 1970-01-01.
fn utc_millis([year, month_zero, day, hour, minute, second, millis]: [i64; 7]) -> Option<i64> {
    if !(1600..=9999).contains(&year) || !(0..12).contains(&month_zero) || !(0..24).contains(&hour)
        || !(0..60).contains(&minute) || !(0..60).contains(&second) || !(0..1000).contains(&millis) { return None; }
    let month = month_zero + 1;
    let leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    let last = match month { 2 => if leap { 29 } else { 28 }, 4 | 6 | 9 | 11 => 30, _ => 31 };
    if !(1..=last).contains(&day) { return None; }
    let y = year - i64::from(month <= 2);
    let m = if month <= 2 { month + 9 } else { month - 3 };
    let days = y * 365 + y / 4 - y / 100 + y / 400 + (153 * m + 2) / 5 + day - 1 - 719468;
    Some((((days * 24 + hour) * 60 + minute) * 60 + second) * 1000 + millis)
}

impl Engine<'_> {
    pub(super) fn utc_calendar_factory(&mut self, path: &mut Path, member: &crate::classfile::MemberRef, args: &[Val]) -> Option<Step> {
        let class = match (member.owner.as_str(), member.name.as_str(), member.descriptor.as_str(), args) {
            ("java/util/TimeZone", "getTimeZone", "(Ljava/lang/String;)Ljava/util/TimeZone;", [Val::R(Some(id))])
                if self.constant_units(path, *id)?.into_iter().eq("UTC".encode_utf16()) => ZONE,
            ("java/util/TimeZone", "getDefault", "()Ljava/util/TimeZone;", []) => ZONE,
            ("java/util/Calendar", "getInstance", "()Ljava/util/Calendar;", []) => CALENDAR,
            ("java/util/Calendar", "getInstance", "(Ljava/util/TimeZone;)Ljava/util/Calendar;", [Val::R(Some(zone))])
                if path.objects[*zone].class == ZONE && path.objects[*zone].fields.contains_key(MARK) => CALENDAR,
            _ => return None,
        };
        if self.gap_mode != GapMode::Strict { return None; }
        let observed = !locale::has_override(path) && self.observed.iter().any(|(c, o)|
            o.on.utc_gregorian && matches!(o.on.zone.as_str(), "UTC" | "Etc/UTC") && path.classes.get(c) == Some(&ClassState::Done));
        if !observed {
            let [id] = args else { return None };
            if class != ZONE || member.name != "getTimeZone" || !self.cp.explicit_utc() { return None; }
            if let Err(stop) = self.reads(path, || "reads UTC from the JDK zone database".into()) { return Some(Err(stop)); }
            self.assumed.insert("the selected JDK uses its bundled, digest-checked tzdb.dat for the explicit UTC identifier".into());
            let zone = self.alloc(path, ZONE);
            // The pinned prototype has zero raw offset, checksum and daylight saving,
            // no transitions or cached last rule. The clone retains the caller's ID reference.
            let field = self.cp.field_key(ZONE, "java/util/TimeZone", "ID");
            path.objects[zone].fields.insert(field, id.clone());
            path.objects[zone].fields.insert(EXPLICIT_ZONE.into(), Val::I(self.b.constant(1, 32)));
            self.push(path, Val::R(Some(zone)));
            self.advance(path);
            return Some(Ok(None));
        }
        if let Err(stop) = self.reads(path, || "reads the JVM calendar startup environment".into()) { return Some(Err(stop)); }
        self.assumed.insert(ASSUMPTION.to_string());
        self.assumption_ids.insert(ASSUMPTION.to_string(), "observed-calendar:gregorian-utc-ad".into());
        let o = self.alloc(path, class);
        path.objects[o].fields.insert(MARK.into(), Val::I(self.b.constant(1, 32)));
        self.push(path, Val::R(Some(o)));
        self.advance(path);
        Some(Ok(None))
    }

    pub(super) fn utc_calendar_method(&mut self, path: &mut Path, o: usize, member: &crate::classfile::MemberRef, args: &[Val]) -> Option<Step> {
        let object = &path.objects[o];
        if object.fields.contains_key(EXPLICIT_ZONE) && matches!((member.name.as_str(), member.descriptor.as_str()),
            ("getID", "()Ljava/lang/String;") | ("setID", "(Ljava/lang/String;)V") | ("getRawOffset" | "getDSTSavings", "()I")
            | ("setRawOffset", "(I)V") | ("useDaylightTime", "()Z")) {
            let (cf, method) = self.cp.find_method(ZONE, &member.name, &member.descriptor)?;
            let mut full = vec![Val::R(Some(o))];
            full.extend_from_slice(args);
            return Some(self.enter_method(path, &member.owner, cf, method, full));
        }
        if !object.fields.contains_key(MARK) { return None; }
        let name = member.name.as_str();
        if (name, member.descriptor.as_str()) == ("getClass", "()Ljava/lang/Class;") {
            let class = object.class.clone();
            let mirror = self.literal(path, Literal::Class(class), "java/lang/Class");
            self.push(path, Val::R(Some(mirror)));
            self.advance(path);
            return Some(Ok(None));
        }
        if object.class == DATE && (name, member.descriptor.as_str()) == ("getTime", "()J") {
            let time = object.fields.get("<time>")?.clone();
            self.push(path, time);
            self.advance(path);
            return Some(Ok(None));
        }
        if object.class != CALENDAR {
            return Some(unsupported(format!("the observed UTC profile does not model {}.{}{}", object.class.replace('/', "."), name, member.descriptor)));
        }
        match (name, member.descriptor.as_str(), args) {
            ("set", "(IIIIII)V", [Val::I(_), Val::I(_), Val::I(_), Val::I(_), Val::I(_), Val::I(_)]) => {
                if let Err(stop) = self.keeps(path, Some(o), "sets calendar fields") { return Some(Err(stop)); }
                for (field, v) in FIELDS.iter().zip(args) { path.objects[o].fields.insert((*field).into(), v.clone()); }
                self.advance(path);
                Some(Ok(None))
            }
            ("set", "(II)V", [Val::I(index), v @ Val::I(_)]) if self.b.constant_value(index) == Some(14) => {
                if let Err(stop) = self.keeps(path, Some(o), "sets calendar milliseconds") { return Some(Err(stop)); }
                path.objects[o].fields.insert(FIELDS[6].into(), v.clone());
                self.advance(path);
                Some(Ok(None))
            }
            ("getTime", "()Ljava/util/Date;", []) | ("getTimeInMillis", "()J", []) => {
                let Some(fields) = FIELDS.iter().map(|key| match object.fields.get(*key) {
                    Some(Val::I(word)) => Some(word.clone()), _ => None,
                }).collect::<Option<Vec<_>>>() else {
                    return Some(unsupported("UTC calendar conversion reads civil fields that were not all set since creation"));
                };
                let fields = std::array::from_fn(|i| &fields[i]);
                let time = match self.finite_words(path, "UTC Gregorian calendar", fields, 64, |engine, raw| {
                    // The JVM's seven parameters are signed int words.
                    let raw = raw.map(|v| i64::from(v as i32));
                    let Some(ms) = utc_millis(raw) else { return unsupported("UTC calendar conversion outside canonical AD dates in years 1600 through 9999"); };
                    Ok(engine.b.constant(ms, 64))
                }) { Ok(time) => Val::J(time), Err(stop) => return Some(Err(stop)) };
                if self.there_before(path, o) {
                    if let Err(stop) = self.reads(path, || "reads a calendar's civil fields".into()) { return Some(Err(stop)); }
                    // Calendar.complete() may populate its fields and flags on a read.
                    if let Err(stop) = self.keeps(path, Some(o), "completes a calendar's civil fields") { return Some(Err(stop)); }
                }
                let result = if name == "getTime" {
                    let date = self.alloc(path, DATE);
                    path.objects[date].fields.insert(MARK.into(), Val::I(self.b.constant(1, 32)));
                    path.objects[date].fields.insert("<time>".into(), time);
                    Val::R(Some(date))
                } else { time };
                self.push(path, result);
                self.advance(path);
                Some(Ok(None))
            }
            _ => Some(unsupported(format!("the observed UTC profile does not model Calendar.{name}{}", member.descriptor))),
        }
    }
}
