import random
from Classes.PlayersClasses import PlayerCard

from Data.ProffesionsData import professions
from Data.BiologyData import biologizes
from Data.HealthData import  healths
from Data.BagadgeData import baggages
from Data.FactsData import facts_one, facts_two
from Data.SpecialData import specials
from Data.ApocalypseData import apocalypses
from Data.BunkersData import bunkers, secrets


def deal_cards():
    return PlayerCard(
        profession=random.choice(professions),
        biology=random.choice(biologizes),
        health=random.choice(healths),
        baggage=random.choice(baggages),
        fact1=random.choice(facts_one),
        fact2=random.choice(facts_two),
        special=random.choice(specials),
        revealed=[]
    )


def get_random_scenario() -> dict:
    return random.choice(apocalypses)


def get_random_bunker() -> dict:
    return random.choice(bunkers)

def get_random_secret() -> str:
    """Случайная секретная особенность бункера из отдельного списка secrets."""
    return random.choice(secrets)