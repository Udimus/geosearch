import os
import re
from getpass import getpass
from typing import List, Tuple

from num2words import num2words
import pandas as pd


ALPHABET = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
ALPHABET_DICT = {letter: index + 1
    for index, letter in enumerate(ALPHABET)
}
DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "data")
SEP = "\t"
ORDINAL_PATTERN = re.compile(r'[0-9]+-[\w]+')
NUM_PATTERN = re.compile(r'[0-9]+')


def load_addresses() -> pd.DataFrame:
    house_addresses_df = pd.read_csv(os.path.join(DATA_PATH, "77_ha.tsv"), sep=SEP)

    house_addresses_df["ordinal_number"] = house_addresses_df["street_name"].apply(
        lambda x: len(ORDINAL_PATTERN.findall(x)) > 0
    )
    
    house_addresses_df["correct"] = house_addresses_df.apply(
        lambda x: not x["house_num"].isalpha() and (x["ordinal_number"] or len(NUM_PATTERN.findall(x["street_name"])) == 0),
        axis=1,
    )

    return house_addresses_df[house_addresses_df["correct"]].copy()

def load_tags(tags: List[str]) -> Tuple[str, pd.DataFrame]:
    house_tags_df = pd.read_csv(os.path.join(DATA_PATH, "77_ht.tsv"), sep=SEP)
    house_tags_df["tag_lower"] = house_tags_df["tag"].apply(lambda x: x.lower())
    tags_lower = [tag.lower() for tag in tags]
    house_tags_filtered = house_tags_df[house_tags_df["tag_lower"].isin(tags_lower)]
    found_tags = house_tags_filtered["tag"].unique().tolist()
    return found_tags, house_tags_filtered[["oid"]].copy()

def num2text(input_string):
    sex = 0
    if input_string[-1] == "я":
        sex = 1
        
    text = num2words(int(input_string.split("-")[0]), lang='ru', to="ordinal")
    
    if sex == 0:
        return text
    if (text[-2:] == "ый") or (text[-2:] == "ой"):
        return text[:-2] + "ая"
    return text[:-2] + "ья"

def process_formula(formula: str) -> Tuple[str, List[int]]:
    letter_index_pattern = re.compile(r'[XxХх]([0-9]+)')
    indices = list(map(int, letter_index_pattern.findall(formula)))
    pattern = re.sub(letter_index_pattern, "{}", formula)
    return pattern, indices

def check_equation(street_name: str, house_num: int, equation_pattern: str, indices: List[int]) -> bool:
    if len(indices) == 0:
        return eval(equation_pattern) == house_num
    if max(indices) > len(street_name):
        return False
    street_nums = [ALPHABET_DICT[street_name[i-1]] for i in indices]
    equation = equation_pattern.format(*street_nums)
    return eval(equation) == house_num

def get_address(x) -> str:
    parts = []
    parts.append("{} {}".format(x["street_name"], x["street_type"]))
    parts.append("{} {}".format(x["house_num"], x["house_type"]))
    if not pd.isnull(x["house_add_1_num"]):
        parts.append("{} {}".format(x["house_add_1_num"], x["house_add_1_type"]))
    if not pd.isnull(x["house_add_2_num"]):
        parts.append("{} {}".format(x["house_add_2_num"], x["house_add_2_type"]))
    return ", ".join(parts)

def hash_tags(tags: List[str]) -> int:
    return hash("".join(sorted(tags)).lower())


class HouseSearcher:
    def __init__(self, tags: List[str]) -> None:
        self._found_tags, house_with_tags = load_tags(tags)
        self._houses_df = load_addresses().merge(house_with_tags)
        self._houses_df["street_name_processed"] = self._houses_df["street_name"].apply(
            lambda x: re.sub(ORDINAL_PATTERN, lambda x: num2text(x.group(0)), x).lower().replace(" ", ""))
        self._houses_df["house_num_processed"] = self._houses_df["house_num"].apply(lambda x: int(re.findall(NUM_PATTERN, x)[0]))

    def __hash__(self):
        return hash_tags(self._found_tags)

    @property
    def found_tags(self) -> List[str]:
        return self._found_tags

    def _search(self, formula: str, subnumbers: str = "no", forced: bool = False) -> List[str]:
        pattern, indices = process_formula(formula)
        mask = self._houses_df["is_active"] | forced
        matches = self._houses_df[
            self._houses_df.apply(
                    lambda x: check_equation(x["street_name_processed"], x["house_num_processed"], pattern, indices),
                    axis=1,
                )
            & mask
        ]
        
        no_subnumbers_mask = (
            pd.isnull(matches["house_add_1_num"])
            & pd.isnull(matches["house_add_2_num"])
            & (matches["house_num"] == matches["house_num_processed"].apply(str))
        )
        
        if subnumbers == "no":
            return matches[no_subnumbers_mask].apply(get_address, axis=1).to_list()
        if subnumbers == "only":
            return matches[~no_subnumbers_mask].apply(get_address, axis=1).to_list()

        return matches.apply(get_address, axis=1).to_list()

    def search(self, formula: str, subnumbers: bool = False) -> List[str]:
        return sorted(self._search(formula, "only" if subnumbers else "no"))

    def get_all_streets(self) -> List[str]:
        return sorted(
            self._houses_df.apply(
                lambda x: x["street_name"] + " " + x["street_type"],
                axis=1,
            ).drop_duplicates().to_list()
        )
