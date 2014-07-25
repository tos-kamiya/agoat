Agoat
======

Agoat, a tool of Arbitrary-Granurality On And-or Tree

## Dependencies

* [Open JDK](http://openjdk.java.net/). Oracle JDK perhaps works (not tested)
* [Soot: a Java Optimization Framework](http://www.sable.mcgill.ca/soot/), enclosed
* [Python](https://www.python.org/)
* [colorama](https://pypi.python.org/pypi/colorama)

## Command-Line Usage

`python ags.py -h` for help message.

Agoat's (Sub-)commands are `disasm`, `index`, `list`, `query`.

`python ags.py COMMAND -h` for help message of a command.

### (1) disasm command

Performs dis-assemble of `.class` or `.jar`.
This step is required because the Agoat analyzer inputs assembly code, not binary.

### (2) index command

Generates index data for searching.
It may take large amount of memory/time for a large input.

### (3) list command

Prints a list of methods or entry points.

### (4) query command

Performs a keyword searching with the index data.

## Short Tutorial

### step 1. Prepare a Java program to be analyzed

Here, a target binary is `MonthlyCalendar.class`.

```bash
~$ cd sample
~/sample$ ls
MonthlyCalendar.java
~/sample$ javac MonthlyCalendar.java
~/sample$ java MonthlyCalendar 2014 7
Sun Mon Tue Wed Thu Fri Sat
         1   2   3   4   5  
 6   7   8   9  10  11  12  
13  14  15  16  17  18  19  
20  21  22  23  24  25  26  
27  28  29  30  31
~/sample$ ls
MonthlyCalendar.class  MonthlyCalendar.java
```

### step 2. Generate an index of the target program

Disassemble the binary file (with `disasm` command)
and generate an index data from it (with `index` command).

```bash
~/sample$ python ags.py disasm .
~/sample$ python ags.py index all
~/sample$ ls
MonthlyCalendar.class  agoat.linenumbertable.gz  javapOutput
MonthlyCalendar.java   agoat.soot_log            sootOutput
agoat.classtable.gz      agoat.summarytable.gz
```

### step 3. Do searching

Specify keywords as parameters `query` command.
Here, keywords are: `set` and `println`.

```bash
~/sample$ python ags.py query set println
---
MonthlyCalendar void printCalendarMonthYear(int,int) {
  java.util.GregorianCalendar void set(int,int,int)	(line: 19)
  MonthlyCalendar void printFields(String[]) {	(line: 25)
    java.io.PrintStream void println(String)	(line: 13)
  }
  MonthlyCalendar void printFields(String[]) {	(line: 33)
    java.io.PrintStream void println(String)	(line: 13)
  }
  MonthlyCalendar void printFields(String[]) {	(line: 38)
    java.io.PrintStream void println(String)	(line: 13)
  }
}
```

## TODOs

* Documents!
* Scalability issues

## License

Agoat is distributed under [MIT License](license/LICENSE_AGOAT).

An enclosed library, Soot, is distributed under [GNU LGPL](license/LICENSE_SOOT).

## Reference

* Toshihiro Kamiya, "An Algorithm for Keyword Search on an Execution Path", In Proc. CSMR-WCRE 2014, pp. 328-332, 2014-02-06.
