"""Builds config/draft_seed.json from the published 2027 mocks and big boards gathered on 2026-11-08.

The weekly pipeline replaces and extends this with live pages and your YouTube board. Edit the lists below
and run `python scripts/make_draft_seed.py` to refresh the starting board by hand.
"""
import json
import pathlib

ALIAS = {
    "Brandon McCoy Jr.": "Brandon McCoy", "Arfan Diane": "Arafan Diane", "Davis Fogel": "Davis Fogle",
    "Ivan Kharchencov": "Ivan Kharchenkov", "Luigi Suino": "Luigi Suigo", "Neo Avdalas": "Neoklis Avdalas",
    "Najai Hines": "Najai Hines", "Baba Oladotun": "Babatunde Oladotun", "Matthew Able": "Matt Able",
    "Miika Muurinen": "Miikka Muurinen", "Abdou Toure": "Abdou Toure", "Billy Richmond": "Billy Richmond III",
    "Bruce Branch": "Bruce Branch III", "Obinna Ekezie": "Obinna Ekezie Jr.",
}

SOURCES = {
    "ESPN": """Tyran Stokes|Jordan Smith Jr.|Caleb Holt|Bruce Branch III|Stefan Joksimovic|Braylon Mullins|Thomas Haugh|Jason Crowe Jr.|
Anthony Thompson|Cameron Williams|Caleb Gaskins|Miikka Muurinen|Austin Goosby|Motiejus Krivas|Luigi Suigo|Matt Able|Alex Condon|
Dame Sarr|Cameron Houindo|Christian Collins|Babatunde Oladotun|Jaxon Richardson|Brandon McCoy|Hugo Yimga-Moukouri|Sayon Keita|
Amari Allen|Ivan Kharchenkov|Patrick Ngongba II|Juke Harris|Tyler Tanner|Malachi Moreno|Cheickh Niang|Colben Landrew|
Obinna Ekezie Jr.|Trey McKenney Jr.|Quentin Coleman|Dylan Mingo|Stefan Vaaks|Milan Momcilovic|Dash Daniels|Massamba Diop|
Tounde Yessoufou|Moustapha Thiam|David Mirkovic|Miles Byrd|Joseph Tugler|Flory Bidunga|Shelton Henderson|Davis Fogle|Jacob Cofie|
Rueben Chinyelu|Billy Richmond III|Neoklis Avdalas|Sam Lewis|Pryce Sandfort|Matas Vokietaitis|Andrej Stojakovic|Jeremy Fears Jr.|
Killyan Toure|John Blackwell""",
    "CBS Sports": """Tyran Stokes|Jordan Smith Jr.|Stefan Joksimovic|Caleb Holt|Bruce Branch III|Amari Allen|Motiejus Krivas|Braylon Mullins|
Patrick Ngongba II|Thomas Haugh|Ivan Kharchenkov|Alijah Arenas|Dame Sarr|Arafan Diane|Quentin Coleman|Luigi Suigo|Cameron Williams|
Davis Fogle|David Mirkovic|Jason Crowe Jr.|Billy Richmond III|Malachi Moreno|Anthony Thompson|Matt Able|Dash Daniels|Neoklis Avdalas|
JJ Andrews|Matas Vokietaitis|Rueben Chinyelu|Tounde Yessoufou""",
    "Sports Illustrated": """Tyran Stokes|Caleb Holt|Stefan Joksimovic|Bruce Branch III|Anthony Thompson|Jordan Smith Jr.|Jason Crowe Jr.|
Colben Landrew|Austin Goosby|Braylon Mullins|JJ Andrews|Thomas Haugh|Matt Able|Quentin Coleman|Amari Allen|Cameron Williams|
Obinna Ekezie Jr.|Motiejus Krivas|Dylan Mingo|Tounde Yessoufou|Ivan Kharchenkov|Najai Hines|Alex Condon|Luigi Suigo|David Mirkovic|
DaKari Spear|Malachi Moreno|Stefan Vaaks|Alijah Arenas|Miikka Muurinen""",
    "Yahoo Sports": """Tyran Stokes|Jordan Smith Jr.|Caleb Holt|Stefan Joksimovic|Bruce Branch III|Thomas Haugh|Amari Allen|Braylon Mullins|
Alijah Arenas|Anthony Thompson|Luigi Suigo|Motiejus Krivas|Flory Bidunga|Patrick Ngongba II|Billy Richmond III|Rueben Chinyelu|
Juke Harris|Tounde Yessoufou|Malachi Moreno|Matt Able|Alex Condon|Tyler Tanner|Milan Momcilovic|Cameron Williams|Miikka Muurinen|
Deron Rippey Jr.|Jamarion Batemon|Nik Khamenia|Babatunde Oladotun|Taylen Kinney""",
    "Bleacher Report": """Tyran Stokes|Caleb Holt|Jordan Smith Jr.|Stefan Joksimovic|Braylon Mullins|Bruce Branch III|Motiejus Krivas|Patrick Ngongba II|
Colben Landrew|Dylan Mingo|Amari Allen|Babatunde Oladotun|Thomas Haugh|Brandon McCoy|Hugo Yimga-Moukouri|Luigi Suigo|JJ Andrews|
Quentin Coleman|Bryson Howard|Anthony Thompson|Alijah Arenas|Abdou Toure|Caleb Gaskins|Tounde Yessoufou|Billy Richmond III|Tyler Tanner|
Nigel James|Davis Fogle|Ivan Kharchenkov|Malachi Moreno""",
    "FanSided": """Tyran Stokes|Stefan Joksimovic|Caleb Holt|Jordan Smith Jr.|Patrick Ngongba II|Quentin Coleman|Brandon McCoy|Colben Landrew|
Bruce Branch III|Motiejus Krivas|David Mirkovic|Anthony Thompson|Malachi Moreno|Ivan Kharchenkov|Abdou Toure|Braylon Mullins|Thomas Haugh|
Tyler Tanner|Najai Hines|Bryson Howard|Dylan Mingo|Arafan Diane|Maximo Adams|Matt Able|Amari Allen|Rueben Chinyelu|Hugo Yimga-Moukouri|
Pryce Sandfort|Dash Daniels|Matas Vokietaitis""",
}

# pos, school, class, height, wingspan, word on the street (written in our own words from the published notes)
P = {
    "Tyran Stokes": ("SF", "Kansas", "Freshman", "6-7", "", "Consensus No. 1. Size, vision and passing set him apart. Shooting, turnovers and consistency are the open questions."),
    "Jordan Smith Jr.": ("PG/SG", "Arkansas", "Freshman", "6-2", "", "Explosive, competitive guard and a strong rebounder for his size. Needs to shoot and run an offense better."),
    "Caleb Holt": ("SG/PG", "Arizona", "Freshman", "6-5", "", "Physical, high floor combo guard who can guard several positions. Shot creation is improving."),
    "Bruce Branch III": ("SG/SF", "BYU", "Freshman", "6-7", "7-1", "Prototype wing size with a good shooting profile. Scouts want more assertiveness on offense."),
    "Stefan Joksimovic": ("PG", "Baskonia (Spain)", "International", "6-7", "", "Slovenian creator who skipped college. Passing and ball handling stand out. Shooting and defense need to show up."),
    "Braylon Mullins": ("SG", "UConn", "Sophomore", "6-6", "", "One of the best shooters in the class. Teams want proof he can do more than shoot."),
    "Thomas Haugh": ("SF/PF", "Florida", "Senior", "6-9", "", "Versatile, high motor forward who returned to school. Will be 24 as a rookie. Three point shot is the swing skill."),
    "Jason Crowe Jr.": ("PG/SG", "Missouri", "Freshman", "6-3", "", "Gifted scorer who can create his own shot. Passing, defense and shot selection get questions."),
    "Anthony Thompson": ("SF/PF", "Ohio State", "Freshman", "6-9", "7-3", "Lefty with length and shooting touch. Motor and consistency are the concerns."),
    "Cameron Williams": ("F/C", "Duke", "Freshman", "6-11", "", "Former top five recruit who runs and stretches the floor. Needs strength, and his role at Duke is not clear yet."),
    "Motiejus Krivas": ("C", "Arizona", "Senior", "7-3", "", "Huge rim protector, seen as the most NBA ready college center. A bigger offensive role could lift him."),
    "Colben Landrew": ("SF", "UConn", "Freshman", "", "", "Connective wing who creates for others and defends multiple spots."),
    "Luigi Suigo": ("C", "Villanova", "", "7-3", "", "Italian big with length and a mix of spacing and rim protection. Stayed out of the 2026 draft."),
    "Amari Allen": ("SF", "Alabama", "Sophomore", "", "", "Returned to school and will handle the ball more, which could raise his stock."),
    "Patrick Ngongba II": ("C", "Duke", "Sophomore", "", "", "Long, broad big who spaces the floor, passes and protects the rim. Health is the key."),
    "Quentin Coleman": ("SG", "Illinois", "Freshman", "", "", "Skilled shooter with great feel. Scouts compare him to Keaton Wagler."),
    "Alijah Arenas": ("SG", "USC", "Sophomore", "", "7-0", "Polarizing wildcard with size and scoring tools, coming off a knee injury."),
    "Ivan Kharchenkov": ("SF", "Arizona", "Sophomore", "", "", "Elite defender and glue player. Offense needs to catch up for him to reach the lottery."),
    "Dame Sarr": ("SF", "Duke", "Sophomore", "", "", "Defensive standout with wing size who shot poorly as a freshman."),
    "Matt Able": ("SG", "North Carolina", "Sophomore", "", "", "Scoring guard with good size who transferred to UNC and should be its centerpiece."),
    "David Mirkovic": ("PF", "Illinois", "Sophomore", "6-9", "", "Skilled, cerebral forward expected to be one of the best players in college. Mobility on defense is a question."),
    "Tyler Tanner": ("PG", "Vanderbilt", "Junior", "6-0", "", "Prolific scorer and passer whose 6-0, 175 pound frame raises size questions."),
    "Dylan Mingo": ("PG", "Baylor", "Freshman", "", "", "Productive when healthy. Must prove he can shoot and run a team."),
    "Malachi Moreno": ("C", "Kentucky", "Sophomore", "", "", "Mobile big with soft hands and high basketball IQ who returned to school."),
    "JJ Andrews": ("SF", "Arkansas", "Freshman", "6-7", "", "Powerful, long athlete with scoring instincts who needs a better perimeter shot."),
    "Billy Richmond III": ("SG/SF", "Arkansas", "Junior", "6-7", "", "Explosive athlete and defender whose jumper is improving."),
    "Tounde Yessoufou": ("SG/SF", "St. John's", "Sophomore", "", "", "Power wing who transferred from Baylor and wants to show more skill and defensive upside."),
    "Rueben Chinyelu": ("C", "Florida", "Senior", "", "7-8", "Strong defender and rebounder with a huge wingspan. Offense is the area to grow."),
    "Alex Condon": ("PF/C", "Florida", "Senior", "7-0", "", "Mobile Australian seven footer whose three point shooting dipped last season."),
    "Miikka Muurinen": ("PF", "Arkansas", "Freshman", "6-11", "", "Mobile, shooting big with clean mechanics. Questions on coachability and consistency."),
    "Babatunde Oladotun": ("SF", "Maryland", "Freshman", "6-10", "", "Former No. 1 recruit and high upside wing who needs to get stronger."),
    "Davis Fogle": ("SG", "Gonzaga", "Sophomore", "", "", "Breakout candidate and jumbo initiator. Needs to hold up his shooting and defense."),
    "Dash Daniels": ("PG/SG", "Melbourne United (Australia)", "International", "", "", "Younger brother of Dyson Daniels and a defense first guard with early offensive progress."),
    "Neoklis Avdalas": ("SF", "North Carolina", "Sophomore", "", "", "Advanced passer who can start the offense as a big wing."),
    "Matas Vokietaitis": ("C", "Texas", "Junior", "7-0", "", "Seven footer with good hands and feet who handles the ball and rebounds."),
    "Austin Goosby": ("PG/SG", "Texas", "Freshman", "", "", "Versatile guard with good size and feel who shot well in high school."),
    "Obinna Ekezie Jr.": ("C", "Louisville", "Freshman", "7-0", "", "Reclassified seven footer with elite rim protection upside who is still raw."),
    "Najai Hines": ("C", "UConn", "Freshman", "", "", "Reclassified big with strong rebounding and shot blocking numbers."),
    "Arafan Diane": ("C", "Houston", "Freshman", "", "", "Top natural big man talent who needs conditioning to maximize his tools."),
    "Caleb Gaskins": ("PF", "Miami", "Freshman", "", "", "Hurricanes freshman forward on the ESPN board."),
    "Shelton Henderson": ("SG", "Miami", "Sophomore", "", "", "Hurricanes guard on the ESPN board."),
    "Juke Harris": ("SG/SF", "Tennessee", "Sophomore", "", "", "Former ACC Most Improved Player who transferred to Tennessee."),
    "Flory Bidunga": ("C", "Louisville", "Junior", "6-9", "", "Defense first interior player who transferred from Kansas."),
    "Milan Momcilovic": ("PF", "Kentucky", "Senior", "6-9", "", "Shooter with limited mobility, especially on defense."),
    "Taylen Kinney": ("PG", "Kansas", "Freshman", "6-3", "", "Scoring point guard playing next to Tyran Stokes at Kansas."),
}


# name: (pos, school, class) for players that only appear on the boards, no notes
MORE = {
    "Cameron Houindo": ("PF", "Cedevita (France)", "International"), "Christian Collins": ("SF", "USC", "Freshman"),
    "Jaxon Richardson": ("SF", "Alabama", "Freshman"), "Brandon McCoy": ("SG", "Michigan", "Freshman"),
    "Hugo Yimga-Moukouri": ("SF", "Nanterre (France)", "International"), "Sayon Keita": ("C", "North Carolina", "Freshman"),
    "Cheickh Niang": ("SG", "Trento (Italy)", "International"), "Trey McKenney Jr.": ("SG", "Michigan", "Sophomore"),
    "Stefan Vaaks": ("SG/PG", "Illinois", "Sophomore"), "Massamba Diop": ("C", "Gonzaga", "Sophomore"),
    "Moustapha Thiam": ("C", "Michigan", "Junior"), "Miles Byrd": ("SG", "Providence", "Senior"),
    "Joseph Tugler": ("PF", "Houston", "Senior"), "Jacob Cofie": ("SF/PF", "USC", "Sophomore"),
    "Sam Lewis": ("SG", "Virginia", "Senior"), "Pryce Sandfort": ("SF", "Nebraska", "Senior"),
    "Andrej Stojakovic": ("SG", "Illinois", "Senior"), "Jeremy Fears Jr.": ("PG", "Michigan State", "Junior"),
    "Killyan Toure": ("SG/PG", "Iowa State", "Sophomore"), "John Blackwell": ("SG", "Duke", "Senior"),
    "DaKari Spear": ("SG/SF", "Texas Tech", ""), "Bryson Howard": ("SG/SF", "Duke", ""), "Abdou Toure": ("SG/SF", "Arkansas", ""),
    "Nigel James": ("PG", "Marquette", ""), "Maximo Adams": ("SF", "North Carolina", ""), "Deron Rippey Jr.": ("PG", "Duke", ""),
    "Jamarion Batemon": ("SG", "Iowa State", ""), "Nik Khamenia": ("G/F", "UConn", ""),
}


def canon(n):
    return ALIAS.get(n, n)


def main():
    out = {"date": "2026-11-08", "cycle": 2027, "sources": {}, "profiles": {}}
    for src, text in SOURCES.items():
        out["sources"][src] = [canon(n.strip()) for n in text.replace("\n", "").split("|") if n.strip()]
    for name, (pos, school, cls, ht, ws, note) in P.items():
        out["profiles"][canon(name)] = {k: v for k, v in
                                        {"pos": pos, "school": school, "class": cls, "height": ht, "wingspan": ws, "note": note}.items() if v}
    for name, (pos, school, cls) in MORE.items():
        out["profiles"].setdefault(canon(name), {k: v for k, v in {"pos": pos, "school": school, "class": cls}.items() if v})
    path = pathlib.Path(__file__).resolve().parent.parent / "config" / "draft_seed.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    names = {n for v in out["sources"].values() for n in v}
    print(path, len(names), "players", {k: len(v) for k, v in out["sources"].items()})


if __name__ == "__main__":
    main()
