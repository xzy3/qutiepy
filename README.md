# qutiepy 
>pronounced: cutie-pie

### Command Summary

`qutiepy [--include/-i EXTRA_ACCOUNTING_FILE] [-s/--skip-accounting] sub_cmd [options] sub_cmd [options]`

A set of administration utilities for interacting with Open/Univa Grid Engine accounting logs.

qutiepy acts as a data processing pipeline similar to the Linux command line. However
accouting records are represented as Python objects rather then text to simplify
complex parsing and formatting.

* `--include/-i` can be added one or more times to include extra files before the system accounting file. 
  These extra files can be compressed. `-` can be used to read standard in.
* `--skip-accounting/-s` Don't use the standard accounting file.
* `--help/-h`
* `--version/-v`

**e.x.**
```bash
qutiepy filter \
  '(and (submission_time.hour >= 9) (submission_time.hour < 12) (submission_time > Jan 2015) (not (qname=all.q)) (ru_wallclock>=300))' \
  format
```

**Note:**
> there is no default command currently and qutiepy does not check. So if you do not 
provide a command you will get nothing but some extra heat from your processor, and wear on
your disks. This probably needs to be fixed.

# Commands
## Variables

All of the variables listed in the [OGE accounting](http://linux.die.net/man/5/sge_accounting) man page
are supported. Python attributes for the appropriate type can be referenced.

* `str` variables
  * qname
  * hostname
  * group
  * owner
  * job_name
  * account
  * project
  * department
  * granted_pe
  * category
  * pe_taskid
* `int` variables
  * job_number
  * priority
  * exit_status
  * ru_ixrss
  * ru_ismrss
  * ru_idrss
  * ru_isrss
  * ru_minflt
  * ru_majflt
  * ru_nswap
  * ru_oublock
  * ru_msgsnd
  * ru_msgrcv
  * ru_nsignals
  * ru_nvcsw
  * ru_nivcsw
  * slots
  * task_number
  * arid 
* `datetime` variables
  * submission_time
  * start_time
  * end_time
  * ar_submission_time
* `float` variables
  * ru_wallclock
  * ru_utime
  * ru_stime
  * ru_inblock
  * cpu
  * iow
  * maxvmem
* `decimal.Decimal` variables
  * ru_maxrss
  * mem
  * io
* special varables
  * failed
* UGE Only `str`
  * cwd
  * submit_cmd

### failed field

This field acts as a specialized integer field. It supports all of the comparison
operations. But it also knows error messages associated with each of its status values:
* `failed.msg` contains just the error message.
* `failed.full` prints the both the status value and the error message e.g. '0 : Successful'
Both of these special values are treated as strings in filtering and formatting operations.

### Differences between Open Grid Engine and Univa Grid Engine

qutiepy automatically determines if a log was written in OGE or UGE format
and automatically chooses the correct parser. And can handle mixed accounting
files automatically. Fields that are encoded differently buy the two supported
GE flavors (`submission_time`, `start_time`, `end_time`, `maxvmem`, `ar_submission_time`)
are regularized to the same size.

UGE includes two fields no available in OGE's logs: `cwd` and `submit_cmd` which
should only be used when you *know* the records are UGE formatted. As they will
cause a panic if the records are requested from a OGE record.

## filter
Select records from the accounting log stream based on an expressive LDAP inspired filter syntax.

### Subcommand Summary

`filter [--help/-h] <filter>`

**e.g.**
>`(and(owner*=Se*)(submission_time.hour >= 9)(submission_time.hour < 17))`
This would match jobs submitted between 9:00 and 17:00 with an owner who's name starts with 'Se'

### Operators

**Note:**
> except for the regex matcher, which is delimited, any whitespace between the operator and
the value is included in the value. Be careful of this when matching strings. The syntax ignores
white space otherwise.

* Supported by all types
  * `(var = value)` equality
  * `(var != value)` inequality
* `str` types only
  * `(var ~= /regex>/flags)` Regex match, uses Python's [re](https://docs.python.org/2/library/re.html) module and syntax.
  * `(var *=glob)` Match strings with the much simpler [glob](https://docs.python.org/2/library/fnmatch.html#fnmatch.fnmatch) style syntax. Globs are case insensitive.
* Numeric and Datetime types
  * `(var op value)` op supports `<`, `>`, `<=`, `>=` with their normal meaning
* Conjunctions: All support one or more predicates
  * `(and predicate [predicate ...])`
  * `(or predicate [predicate ...])`
  * `(not predicate [predicate ...])`
  
#### Datetime notes

When parsing values to be matched to Datetime fields the powerful [dateutil.parse](https://dateutil.readthedocs.org/en/latest/parser.html) is used which allows
for flexiable human friendly entry of dates and times such as `January 2014` or `9 am Feb 2, 2015`. The parser is
quite forgiving so give it a shot. The most important thing to be aware of is that these are absolute epocs.

If you want to match based on time of day you should use `field.hour` and `field.minute`; or `field.month`, `field.day`, `field.year`
for recurring matches based on the month, day of month, or year.

**Note:**
>If you want to match on the day of the week you're currently out of luck. Datetime's `weekday` and `isoweekday` are methods
rather than attributes. This also probably needs to be fixed.
  
#### Regex Notes

* The `/` character can actually be any character. The first non-witespace character encountered is
  used to start the pattern. The pattern continues until that exact character is encounterd again.
* The flags field is any combination of the single character flags in the python module
  * `I` [Ignore Case](https://docs.python.org/2/library/re.html#re.I)
  * `L` [Locale](https://docs.python.org/2/library/re.html#re.L)
  * `M` [Multiline](https://docs.python.org/2/library/re.html#re.M)
  * `S` [Dot all](https://docs.python.org/2/library/re.html#re.S)
  * `U` [Unicode](https://docs.python.org/2/library/re.html#re.U)
  * `X` [Verbose](https://docs.python.org/2/library/re.html#re.X)

## format
Print record strings based on Python's [string formatting](https://docs.python.org/2/library/string.html#format-string-syntax)
mini language.

Datetime fields do understand [strftime formatting](https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior) like
a Python programmer would expect.

### Sub-Command Summary

`format [--help/-h] [--output/-o file] <format str>`

* `--output/-o` Output to this file rather than Standard Out

### Special format conversion
A custom numetrical conversion flag `h` has been added, which prints a number with a SI prefix 
  
**e.g.**
>`{maxvmem!h}b` might print `12.20Kb`

### default print format
The default format string is a slightly improved version of the output of ```qacct -j $JOB_ID``` for the same record.

To give you an idea of the syntax this is the default formatting string:
```
==============================================================
qname           {qname}
hostname        {hostname}
group           {group}
owner           {owner}
project         {project}
department      {department}
jobname         {job_name}
jobnumber       {job_number}
taskid          {task_number}
pe_taskid       {pe_taskid}
account         {account}
priority        {priority}
qsub_time       {submission_time:%x %X}
start_time      {start_time:%x %X}
end_time        {end_time:%x %X}
waiting_time    {waiting_time}
aggregate_time  {aggregate_time}
granted_pe      {granted_pe}
slots           {slots}
failed          {failed.full}
exit_status     {exit_status}
ru_wallclock    {ru_wallclock}
ru_utime        {ru_utime}
ru_stime        {ru_stime}
ru_maxrss       {ru_maxrss!h}
ru_ixrss        {ru_ixrss!h}
ru_ismrss       {ru_ismrss!h}
ru_idrss        {ru_idrss!h}
ru_isrss        {ru_isrss!h}
ru_minflt       {ru_minflt}
ru_majflt       {ru_majflt}
ru_nswap        {ru_nswap}
ru_inblock      {ru_inblock}
ru_oublock      {ru_oublock}
ru_msgsnd       {ru_msgsnd}
ru_msgrcv       {ru_msgrcv}
ru_nsignals     {ru_nsignals}
ru_nvcsw        {ru_nvcsw}
ru_nivcsw       {ru_nivcsw}
cpu             {cpu}
mem             {mem}
io              {io}
iow             {iow}
maxvmem         {maxvmem!h}b
arid            {arid}
```
