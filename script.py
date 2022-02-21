import regex
import sys
from collections import defaultdict, Counter


class Candidate(str):
    
    def __init__(self, value):
        super().__init__()
        self.start = 0
        self.stop = 0

    def set_position(self, start, stop):
        self.start = start
        self.stop = stop

class ExtractAcronymDefinitionPair:

    def __init__(self):
        pass

    def _yield_lines_from_file(self,file_path):
        with open(file_path, 'rb') as f:
            for line in f:
                try:
                    line = line.decode('utf-8')
                except UnicodeDecodeError:
                    line = line.decode('latin-1').encode('utf-8').decode('utf-8')
                line = line.strip()
                yield line

    def _yield_lines_from_doc(self,doc_text):
        for line in doc_text.split("\n"):
            yield line.strip()

    def _best_candidates(self,sent):

        if '(' in sent:
            # Check some things first
            if sent.count('(') != sent.count(')'):
                raise ValueError("Unbalanced parentheses: {}".format(sent))

            if sent.find('(') > sent.find(')'):
                raise ValueError("First parentheses is right: {}".format(sent))

            close_index = -1
            while 1:
                open_index = sent.find(' (', close_index + 1)
                if open_index == -1: break
                open_index += 1
                close_index = open_index + 1
                open_count = 1
                skip = False
                while open_count:
                    try:
                        char = sent[close_index]
                    except IndexError:
                        skip = True
                        break
                    if char == '(':
                        open_count += 1
                    elif char in [')', ';', ':']:
                        open_count -= 1
                    close_index += 1

                if skip:
                    close_index = open_index + 1
                    continue

                start = open_index + 1
                stop = close_index - 1
                candidate = sent[start:stop]

                start = start + len(candidate) - len(candidate.lstrip())
                stop = stop - len(candidate) + len(candidate.rstrip())
                candidate = sent[start:stop]

                if self._conditions(candidate):
                    new_candidate = Candidate(candidate)
                    new_candidate.set_position(start, stop)
                    yield new_candidate

    def _conditions(self,candidate):

        viable = True
        if regex.match(r'(\p{L}\.?\s?){2,}', candidate.lstrip()):
            viable = True
        if len(candidate) < 2 or len(candidate) > 10:
            viable = False
        if len(candidate.split()) > 2:
            viable = False
        if not regex.search(r'\p{L}', candidate):
            viable = False
        if not candidate[0].isalnum():
            viable = False

        return viable

    def _get_definition(self,candidate, sent):

        tokens = regex.split(r'[\s\-]+', sent[:candidate.start - 2].lower())
        key = candidate[0].lower()
        first_chars = [t[0] for t in filter(None, tokens)]
        definition_freq = first_chars.count(key)
        candidate_freq = candidate.lower().count(key)

        if candidate_freq <= definition_freq:
            count = 0
            start = 0
            start_index = len(first_chars) - 1
            while count < candidate_freq:
                if abs(start) > len(first_chars):
                    raise ValueError("candidate {} not found".format(candidate))
                start -= 1
                try:
                    start_index = first_chars.index(key, len(first_chars) + start)
                except ValueError:
                    pass

                count = first_chars[start_index:].count(key)

            start = len(' '.join(tokens[:start_index]))
            stop = candidate.start - 1
            candidate = sent[start:stop]

            start = start + len(candidate) - len(candidate.lstrip())
            stop = stop - len(candidate) + len(candidate.rstrip())
            candidate = sent[start:stop]
            new_candidate = Candidate(candidate)
            new_candidate.set_position(start, stop)
            return new_candidate

        else:
            raise ValueError('There are less keys in the tokens in front of candidate than there are in the candidate')

    def _select_definition(self,definition, abbrev):

        if len(definition) < len(abbrev):
            raise ValueError('Abbreviation is longer than definition')

        if abbrev in definition.split():
            raise ValueError('Abbreviation is full word of definition')

        s_index = -1
        l_index = -1

        while 1:
            try:
                long_char = definition[l_index].lower()
            except IndexError:
                raise

            short_char = abbrev[s_index].lower()

            if not short_char.isalnum():
                s_index -= 1

            if s_index == -1 * len(abbrev):
                if short_char == long_char:
                    if l_index == -1 * len(definition) or not definition[l_index - 1].isalnum():
                        break
                    else:
                        l_index -= 1
                else:
                    l_index -= 1
                    if l_index == -1 * (len(definition) + 1):
                        raise ValueError("definition {} was not found in {}".format(abbrev, definition))

            else:
                if short_char == long_char:
                    s_index -= 1
                    l_index -= 1
                else:
                    l_index -= 1

        new_candidate = Candidate(definition[l_index:len(definition)])
        new_candidate.set_position(definition.start, definition.stop)
        definition = new_candidate

        tokens = len(definition.split())
        length = len(abbrev)

        if tokens > min([length + 5, length * 2]):
            raise ValueError("did not meet min(|A|+5, |A|*2) constraint")

        if definition.count('(') != definition.count(')'):
            raise ValueError("Unbalanced parentheses not allowed in a definition")

        return definition

    def extract(self,file_path=None,doc_text=None,most_common_definition=False,first_definition=False):
        abbrev_map = dict()
        list_abbrev_map = defaultdict(list)
        counter_abbrev_map = dict()
        omit = 0
        written = 0
        if file_path:
            sentence_iterator = enumerate(self._yield_lines_from_file(file_path))
        elif doc_text:
            sentence_iterator = enumerate(self._yield_lines_from_doc(doc_text))
        else:
            return abbrev_map

        
        collect_definitions = True if most_common_definition or first_definition else False

        for i, sentence in sentence_iterator:
            clean_sentence = regex.sub(r'([(])[\'"\p{Pi}]|[\'"\p{Pf}]([);:])', r'\1\2', sentence)
            try:
                for candidate in self._best_candidates(clean_sentence):
                    try:
                        definition = self._get_definition(candidate, clean_sentence)
                    except (ValueError, IndexError) as e:
                        print(f"{i} Omitting candidate {candidate}. Reason: {e.args[0]}")
                        omit += 1
                    else:
                        try:
                            definition = self._select_definition(definition, candidate)
                        except (ValueError, IndexError) as e:
                            print(f"{i} Omitting definition {definition} for candidate {candidate}. Reason: {e.args[0]}")
                            omit += 1
                        else:
                            if collect_definitions:
                                list_abbrev_map[candidate].append(definition)
                            else:
                                abbrev_map[candidate] = definition
                            written += 1
            except (ValueError, IndexError) as e:
                print(f"{i} Error processing sentence {sentence}: {e.args[0]}")
        print(f"{written} abbreviations detected and kept ({omit} omitted)")

        if collect_definitions:
            if most_common_definition:
                for k,v in list_abbrev_map.items():
                    counter_abbrev_map[k] = Counter(v).most_common(1)[0][0]
            else:
                for k, v in list_abbrev_map.items():
                    counter_abbrev_map[k] = v[0]
            return counter_abbrev_map

        return abbrev_map
    
    
    if __name__ == "__main___":
        text =" I studied in Delhi University (DU) where I studied Bachelor in Science (B.Sc). I live in New Delhi whihc is an National Capital Region (NCR)"
        obj = ExtractAcronymDefinitionPair()
        print(obj.extract(doc_text=text))
        
#3 abbreviations detected and kept (0 omitted)
#{'B.Sc': 'Bachelor in Science', 'DU': 'Delhi University', 'NCR': 'National Capital Region'}
