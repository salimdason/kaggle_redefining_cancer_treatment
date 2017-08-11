# coding=utf-8
from configuration import *
import zipfile
import re
import os
import csv
import sys
import urllib2
from bs4 import BeautifulSoup
import unicodedata
import copy

# increase max csv file in order to load the datasets
csv.field_size_limit(sys.maxsize)


####################################################################################################


def extract_zip_file(filepath, directory):
    """
    Extracts a zip file into a directory
    :param str filepath: zip file path
    :param str directory: directory to extract the file
    """
    zip_ref = zipfile.ZipFile(filepath, 'r')
    zip_ref.extractall(directory)
    zip_ref.close()


def extract_zip_files():
    """
    Extracts the data zip files into the data folder
    """
    files = ['training_text', 'training_variants', 'test_text', 'test_variants']
    for file in files:
        filepath = os.path.join(DIR_DATA, file)
        if not os.path.exists(filepath):
            extract_zip_file('{}.zip'.format(file), DIR_DATA)


def load_csv_dataset(filename):
    """
    Loads a csv filename as a dataset
    :param str filename: name of the file
    :return List[DataSample]: a list of DataSample
    """
    dataset = []
    with open(os.path.join(DIR_GENERATED_DATA, filename)) as file:
        reader = csv.reader(file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for row in reader:
            id = int(row[0])
            text = row[1]
            gene = row[2]
            variation = row[3]
            try:
                real_class = int(row[4])
            except:
                real_class = None
            dataset.append(DataSample(id, text, gene, variation, real_class))
    return dataset


def save_csv_dataset(filename, dataset):
    """
    Saves a dataset into a file
    :param str filename: name of the file
    :param List[DataSample] dataset: dataset
    """
    with open(os.path.join(DIR_GENERATED_DATA, filename), 'wb') as file:
        writer = csv.writer(file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        # for d in dataset:
        for i, d in enumerate(dataset):
            writer.writerow([str(d.id), d.text, d.gene, d.variation, str(d.real_class)])


def load_csv_wikipedia_gen(filename):
    """
    Loads a csv filename as a wikipedia genes dataset
    :param str filename: name of the file
    :return List[WikipediaGene]: a list of WikipediaGene
    """
    dataset = []
    with open(os.path.join(DIR_GENERATED_DATA, filename)) as file:
        reader = csv.reader(file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for row in reader:
            dataset.append(WikipediaGene(row[0], row[1]))
    return dataset


def save_csv_wikipedia_gen(filename, wikipedia_genes):
    """
    Saves the wikipedia genes into a file
    :param str filename: name of the file
    :param List[WikipediaGene] wikipedia_genes: WikipediaGene dataset
    """
    with open(os.path.join(DIR_GENERATED_DATA, filename), 'wb') as file:
        writer = csv.writer(file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for d in wikipedia_genes:
            writer.writerow([str(d.gene), d.text])


####################################################################################################


class DataSample(object):
    """
    Class that represents a data sample. The data samples of the training and test sets will be load
    in this class and the data will also preprocessed in this class.
    """

    def __init__(self, id, text, gene, variation, real_class=None):
        """
        :param int id:id of the sample
        :param str text: text of the sample
        :param str gene: gene related with the text
        :param str variation: variation related with the text
        :param int real_class: class of the sample, it can be None for the test dataset
        """
        self.id = id
        self.text = text
        self.gene = gene
        self.variation = variation
        self.real_class = real_class

    def __copy__(self):
        text_copy = copy.deepcopy(self.text)
        return DataSample(self.id, text_copy, self.gene, self.variation, self.real_class)


def load_raw_dataset(text_file, variants_file):
    """
    loads the raw dataset into a list of samples where echa sample has
    :param str text_file: the file with the text data
    :param str variants_file: the file with the variants data
    :return List[DataSample]: a list of DataSample
    """
    with open(os.path.join(DIR_DATA, text_file)) as file:
        lines = file.readlines()
        data_text = lines[1:]  # ignore header
    with open(os.path.join(DIR_DATA, variants_file)) as file:
        lines = file.readlines()
        data_variant = lines[1:]  # ignore header
        header_variants = lines[0].split(',')
    data = []
    for dataline_text, dataline_variant in zip(data_text, data_variant):
        dataline_text_split = dataline_text.split('||')
        dataline_variant_split = dataline_variant.split(',')
        # basic checks
        if len(dataline_text_split) != 2:
            raise Exception('error in text file in line {}'.format(dataline_text))
        if len(dataline_variant_split) < 3 or len(dataline_variant_split) > 4:
            raise Exception('error in variant file in line {}'.format(dataline_variant))
        if dataline_text_split[0] != dataline_variant_split[0]:
            msg = 'wrong ids in text and variant files {} !+ {}'
            raise Exception(msg.format(dataline_text_split[0], dataline_variant_split[0]))
        id = int(dataline_text_split[0].strip())
        text = dataline_text_split[1].strip()
        gene = dataline_variant_split[1].strip()
        variation = dataline_variant_split[2].strip()
        if len(header_variants) == 4:
            real_class = int(dataline_variant_split[3].strip())
        else:
            real_class = None
        data.append(DataSample(id, text, gene, variation, real_class))
    return data


####################################################################################################


def load_or_clean_text_dataset(filename, dataset,
                               saving_fn=save_csv_dataset,
                               loading_fn=load_csv_dataset):
    """
    Loads the clean dataset from a file if it exits or cleans the dataset and saves it to the file
    :param srt filename: the filename to store the clean dataset or loads it.
    :param List[DataSample] dataset: dataset
    :return: List[DataSample]
    :param saving_fn: The function used to save the dataset
    :param loading_fn: The function used to load the dataset
    """
    if not os.path.exists(os.path.join(DIR_GENERATED_DATA, filename)):
        for datasample in dataset:
            datasample.text = clean_text(datasample.text)
        saving_fn(filename, dataset)
    return loading_fn(filename)


# regular expressions to clean up the text

RE_BIBLIOGRAPHIC_REFERENCE_1 = re.compile(r"\s*\[[\d\s,]+\]\s*")
RE_BIBLIOGRAPHIC_REFERENCE_2 = re.compile(r"\s*\(([a-zA-Z\s\.,]+\d{2,4}\s*;?)+\s*\)\s*")
RE_BIBLIOGRAPHIC_REFERENCE_3 = re.compile(r"\s*\[([a-zA-Z\s\.,]+\d{2,4}\s*;?)+\s*\]\s*")
RE_BIBLIOGRAPHIC_REFERENCE_4 = re.compile(r"\s*\([\d,\s]+\)\s*")
RE_BIBLIOGRAPHIC_REFERENCE_5 = re.compile(r"\s*(\w+ et al\.,?)+")

RE_FIGURES = re.compile(r"\s*(Fig(ure)?\.? [\w,]+)\s*")
RE_TABLES = re.compile(r"\s*(Table\.? [\w,]+)\s*")
RE_WHITE_SPACES = re.compile(r"\s+")
RE_EMTPY_PARENTHESES = re.compile(r"\(\s*(and)?\s*\)")


def clean_text(text):
    """
    Cleans a text: removes bibliographic references, references to figures and tables, empty
    parentheses and adds extra space for the symbols.
    :param str text: the original text
    :return str: the clean text
    """
    # remove bibliographic references
    text = re.sub(RE_BIBLIOGRAPHIC_REFERENCE_1, ' ', text)
    text = re.sub(RE_BIBLIOGRAPHIC_REFERENCE_2, ' ', text)
    text = re.sub(RE_BIBLIOGRAPHIC_REFERENCE_3, ' ', text)
    text = re.sub(RE_BIBLIOGRAPHIC_REFERENCE_4, ' ', text)
    text = re.sub(RE_BIBLIOGRAPHIC_REFERENCE_5, ' ', text)
    # remove figures
    text = re.sub(RE_FIGURES, "", text)
    # remove tables
    text = re.sub(RE_TABLES, "", text)
    # remove empty parentheses
    text = re.sub(RE_EMTPY_PARENTHESES, "", text)
    # add white spaces before and after symbols
    text = text.replace('...', '.')
    for symbol in ['(', ')', '/', '-', '\xe2', '\'', '\"', '%', ':', '?', ', ', '. ', '<', '>',
                   '=', '-', ';', '!', '°C', '*']:
        text = text.replace(symbol, ' {} '.format(symbol))
    # remove double white spaces
    text = re.sub(RE_WHITE_SPACES, ' ', text)
    return text


####################################################################################################


def group_count(elements, group=None):
    """
    Groups the elements of elements in the groups dictionary
    :param List[List[str]] elements: A list of str or a recursive list of lists of str
    :param Dict[] group: where to group the elements, used for recursion
    :return Dict[str, int]: dictionary with the number (value) of each element (key)
    """
    if group is None:
        group = {}
    for e in elements:
        if isinstance(e, list):
            group = group_count(e, group)
        elif e in group:
            group[e] += 1
        else:
            group[e] = 1
    return group


def show_stats(train_set, test_set):
    """
    Shows some statistics of the datasets
    :param List[DataSample] train_set: training set
    :param List[DataSample] test_set: test set
    """
    print("{} samples in the training set".format(len(train_set)))
    print("{} samples in the test set".format(len(test_set)))
    classes = [d.real_class for d in train_set]
    classes_group = group_count(classes)
    classes_string = ", ".join(
        ["{}:{}".format(k, classes_group[k]) for k in sorted(classes_group.keys())])
    print("{} different classes: {}".format(len(set(classes)), classes_string))
    train_genes = [d.gene for d in train_set]
    test_genes = [d.gene for d in test_set]
    print("{} genes in training set".format(len(set(train_genes))))
    print("{} genes in test set".format(len(set(test_genes))))
    print("{} genes in test and train set".format(len(set(test_genes + train_genes))))


####################################################################################################

class WikipediaGene(object):
    """
    Class that represents the text of a gene from the wikipedia.
    """

    def __init__(self, gene, text):
        """
        :param str gene: gene
        :param str text: text of the gene
        """
        self.gene = gene
        self.text = text


def get_genes_articles_from_wikipedia(genes):
    """
    Loads the data from the wikipedia genes from the files in DIR_WIKIPEDIA_GENES or retrieves them
    from internet and saves the information into the files
    :param List[str] genes: the list of gene names
    :return List[str,str]:
    """
    data = []
    for gen in genes:
        filename = os.path.join(DIR_WIKIPEDIA_GENES, 'wikipedia_gen_{}'.format(gen))
        if not os.path.exists(filename):
            url = 'https://en.wikipedia.org/wiki/{}'.format(gen)
            try:
                html = BeautifulSoup(urllib2.urlopen(url).read(), 'lxml')
                html_data = html.find(id='mw-content-text').div.find_all('p')
                text_data = [h.get_text().strip() for h in html_data]
                text_data = [t for t in text_data if len(t) > 30 and len(t.split()) > 10]
                text_data = [unicodedata.normalize('NFKD', l)
                                 .encode('ascii', 'ignore') for l in text_data]
            except:
                text_data = ['']
            with open(filename, 'wb') as f:
                f.writelines(text_data)
        with open(filename, 'r') as f:
            text_lines = f.readlines()
            text = '\n'.join(text_lines)
        data.append(WikipediaGene(gen, text))
    return data


####################################################################################################


def load_or_parse_mutations_dataset(filename, dataset, genes,
                                    saving_fn=save_csv_dataset,
                                    loading_fn=load_csv_dataset):
    """
    Loads the parsed dataset of DataSample or WikipediaGenes from a file if it exits or parses the
    dataset and saves it to the file
    :param srt filename: the filename to store the dataset or loads it.
    :param List[DataSample|WikipediaGene] dataset: dataset
    :param saving_fn: The function used to save the dataset
    :param loading_fn: The function used to load the dataset
    :return List[DataSample|WikipediaGene]:
    """
    if not os.path.exists(os.path.join(DIR_GENERATED_DATA, filename)):
        for datasample in dataset:
            words = datasample.text.split()
            parsed_words = []
            for word in words:
                if is_mutation(word, genes):
                    parsed_words.extend(split_mutation(word))
                else:
                    parsed_words.append(word)
            datasample.text = ' '.join(parsed_words)
        saving_fn(filename, dataset)
    return loading_fn(filename)


def is_mutation(word, genes):
    """
    Checks whether a word is a mutation or not. This method assumes a mutation is not a gene and at
    least one of the next conditions:
    - has a _ character
    - has digits and 2 or more upper case letters
    - has 3 digits and at least 1 upper case letter
    - has at least 1 digits, at least 1 upper case letters and at least 1 symbols
    - has at least 1 digits and at least 1 lower case letter
    - has a _ character and 2 or more upper case letters
    - has lower case letters and 2 or more upper case leters
    :param str word: The word to check
    :param List[str] genes: The list of genes
    :return bool: True if the word is mutation False otherwise
    """
    word = word.strip()
    if len(word) >= 3 and word not in genes:
        has_hyphen_minus = '_' in word
        has_hyphen = '-' in word
        has_digits = any(ch.isdigit() for ch in word)
        has_three_digits = sum(1 for ch in word if ch.isdigit()) > 2
        has_upper_case = any(ch.isupper() for ch in word)
        has_two_upper_case = sum(1 for ch in word if ch.isupper()) > 1
        has_lower_case = any(ch.islower() for ch in word)
        has_symbols = any(not ch.isalnum() for ch in word)
        return has_hyphen_minus or \
               (has_digits and has_two_upper_case) or \
               (has_three_digits and has_upper_case) or \
               (has_digits and has_upper_case and has_symbols) or \
               (has_digits and has_lower_case) or \
               (has_hyphen and has_two_upper_case) or \
               (has_lower_case and has_two_upper_case)
    return False


def split_mutation(word):
    """
    Splits a mutation in symbols. It first split the word with some keywords (del, ins, dup, ...)
    and them splits all the rest of letters. Per every element generated a symbol is created adding
    the symbol > before the letter or string.
    :param str word: the mutation to split
    :return List[str]: a list of symbols
    """
    word = word.strip()
    for symbol in ['del', 'ins', 'dup', 'trunc', 'splice', 'fs', 'null', 'Fusion', '#', '+']:
        word = word.replace(symbol, ' >{} '.format(symbol))
    i = 0
    new_words = []
    while i < len(word):
        if word[i] == '>':
            j = i + 1
            while j < len(word) and word[j] != ' ':
                j += 1
            new_words.append('{}'.format(word[i:j]))
            i = j
        elif word[i] != ' ':
            new_words.append('>{}'.format(word[i]))
            i += 1
        else:
            i += 1
    return new_words


####################################################################################################


def load_or_parse_numbers_dataset(filename, dataset,
                                  saving_fn=save_csv_dataset,
                                  loading_fn=load_csv_dataset):
    """
    Loads the parsed dataset from a file or parses a dataset of DataSample or WikipediaGene to
    transform all the numbers into symbols and saves it into the file.
    :param filename: name of the file
    :param List[DataSample|WikipediaGene] dataset: the datset of DataSample or WikipediaGene
    :param saving_fn: The function used to save the dataset
    :param loading_fn: The function used to load the dataset
    :return List[DataSample|WikipediaGene]: the datset
    """
    if not os.path.exists(os.path.join(DIR_GENERATED_DATA, filename)):
        for datasample in dataset:
            words = datasample.text.split()
            parsed_words = []
            for word in words:
                try:
                    number = float(word)
                    parsed_words.append(encode_number(number))
                except ValueError:
                    parsed_words.append(word)
            datasample.text = ' '.join(parsed_words)
        saving_fn(filename, dataset)
    return loading_fn(filename)


####################################################################################################


def encode_number(number):
    """
    Encodes the number as a symbol. The buckets are:
     (-inf, 0.001, 0.01, 0.1, 1.0, 10.0, 25.0, 50.0, 75.0, 100.0, +inf)
    :param float number: a float number
    :return str: the encoded number
    """
    if number < 0.001:
        return '>number_0001'
    elif number < 0.01:
        return '>number_001'
    elif number < 0.1:
        return '>number_01'
    elif number < 1.0:
        return '>number_1'
    elif number < 10.0:
        return '>number_10'
    elif number < 25.0:
        return '>number_25'
    elif number < 50.0:
        return '>number_50'
    elif number < 75.0:
        return '>number_75'
    elif number < 100.0:
        return '>number_100'
    else:
        return '>number_1000'


if __name__ == '__main__':
    if not os.path.exists(DIR_GENERATED_DATA):
        os.makedirs(DIR_GENERATED_DATA)
    if not os.path.exists(DIR_DATA_WORD2VEC):
        os.makedirs(DIR_DATA_WORD2VEC)
    if not os.path.exists(DIR_WIKIPEDIA_GENES):
        os.makedirs(DIR_WIKIPEDIA_GENES)
    print('Extract zip files if not already done...')
    extract_zip_files()
    print('Load raw data...')
    train_set = load_raw_dataset('training_text', 'training_variants')
    test_set = load_raw_dataset('test_text', 'test_variants')
    print('Clean raw data or load already clean data...')
    train_set = load_or_clean_text_dataset('train_set_text_clean', train_set)
    test_set = load_or_clean_text_dataset('test_set_text_clean', test_set)
    print('Statistics about the data:')
    show_stats(train_set, test_set)
    genes = set([s.gene for s in train_set] + [s.gene for s in test_set])
    variations = set([s.variation for s in train_set] + [s.variation for s in test_set])
    if not all(is_mutation(word, genes) for word in variations):
        wrong_detections = sorted(
            set([word.strip() for word in variations if not is_mutation(word, genes)]))
        print('WARNING not all variations are detected as mutations: {}'.format(
            ", ".join(wrong_detections)))
    print('Parse mutations to tokens...')
    train_set = load_or_parse_mutations_dataset('train_set_mutations_parsed', train_set, genes)
    test_set = load_or_parse_mutations_dataset('test_set_mutations_parsed', test_set, genes)
    print('Parse numbers to tokens...')
    train_set = load_or_parse_numbers_dataset('train_set_numbers_parsed', train_set)
    test_set = load_or_parse_numbers_dataset('test_set_numbers_parsed', test_set)
    print('Download articles from wikipedia about genes...')
    genes_articles = get_genes_articles_from_wikipedia(genes)
    print('Clean articles from wikipedia or load already clean data...')
    genes_articles = load_or_clean_text_dataset('wikipedia_text_clean', genes_articles,
                                                saving_fn=save_csv_wikipedia_gen,
                                                loading_fn=load_csv_wikipedia_gen)
    print('Parse mutations to tokens from wikipedia articles...')
    genes_articles = load_or_parse_mutations_dataset('wikipedia_mutations_parsed',
                                                     genes_articles, genes,
                                                     saving_fn=save_csv_wikipedia_gen,
                                                     loading_fn=load_csv_wikipedia_gen)
    print('Parse numbers to tokens from wikipedia articles...')
    genes_articles = load_or_parse_numbers_dataset('wikipedia_numbers_parsed',
                                                   genes_articles,
                                                   saving_fn=save_csv_wikipedia_gen,
                                                   loading_fn=load_csv_wikipedia_gen)
