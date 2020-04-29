#!/usr/bin/env python3
'''
Compare result with answer.
'''
import argparse
import csv
import json
import os
import warnings

import pandas as pd


def _upper(item):
    if item == '':
        return None
    if isinstance(item, str):
        return item.upper()
    return item


class Answer():  # pylint: disable=too-few-public-methods
    '''Structure of ground truth'''

    __slots__ = ['fault_id', 'category', 'cmdb_id', 'candidates']

    def __init__(self, category, cmdb_id, candidates):
        self.category = str(category).upper()
        self.cmdb_id = str(cmdb_id).upper()
        self.candidates = {_upper(candidate) for candidate in candidates}

    def __repr__(self):
        data = {
            'category': self.category,
            'cmdb_id': self.cmdb_id,
            'candidates': self.candidates,
        }
        return str(data)


class Result():  # pylint: disable=too-few-public-methods
    '''Structure of submitted answer'''

    __slots__ = ['fault_id', 'rank', 'category', 'cmdb_id', 'index']

    def __init__(self, category, cmdb_id, index):
        self.category = category.upper()
        self.cmdb_id = cmdb_id.upper()
        self.index = _upper(index)

    def is_correct(self, answer):
        '''
        Compare result with ground truth.
        '''
        return self.category == answer.category and \
            self.cmdb_id == answer.cmdb_id and \
            self.index in answer.candidates

    def __repr__(self):
        data = {
            'category': self.category,
            'cmdb_id': self.cmdb_id,
            'index': self.index,
        }
        return str(data)


def _load_answer(path):
    data = {}
    message = ''
    try:
        if path.endswith('.hdf'):
            reader = pd.read_hdf(path)
            for _, (fault_id, category, cmdb_id, candidate) in reader.iterrows():
                if fault_id not in data:
                    data[fault_id] = Answer(category, cmdb_id, [])
                data[fault_id].candidates.add(_upper(candidate))
        else:
            with open(path) as obj:
                data = json.load(obj)
                for fault_id in data:
                    data[fault_id] = Answer(*data[fault_id])
    except:  # pylint: disable=bare-except
        message = 'Failed to parse "%s"' % (path, )

    return data, message


def _load_data(path):
    data = {}
    message = ''
    try:
        with open(path) as obj:
            if path.endswith('.csv'):
                reader = csv.reader(obj)
                next(reader)  # header
                for fault_id, rank, category, cmdb_id, index in reader:
                    if fault_id not in data:
                        data[fault_id] = []
                    data[fault_id].append((rank, Result(category, cmdb_id, index)))
                for fault_id in data:
                    ranks = sorted(data[fault_id], key=lambda item: item[0])
                    data[fault_id] = [result for _, result in ranks]
            else:
                data = json.load(obj)
                for fault_id in data:
                    data[fault_id] = [Result(*item) for item in data[fault_id]]
    except:  # pylint: disable=bare-except
        message = 'Failed to parse "%s"' % (path, )
    return data, message


def get_rank(results, answer):
    '''Get the rank of correct result'''
    for index, result in enumerate(results):
        if result.is_correct(answer):
            return index
    return None


def judge(answer_path, result_path, grade_gradient=(100, 20)):
    '''
    Compare the submitted answer with ground truth, with a grade returned.
    '''
    print('"%s" is to be submitted, judged by "%s"' %
          (result_path, answer_path))
    message = []
    # 1. Prepare data
    answers, error = _load_answer(answer_path)
    if error:
        message.append(error)
    results, error = _load_data(result_path)
    if error:
        message.append(error)
    print('Fault Count: %d. Result Count: %d' %
          (len(answers), len(results)))
    print('\n'.join(message))

    # 2. Grade
    grade = 0
    for i in answers:
        if i not in results:
            continue
        rank = get_rank(results[i], answers[i])
        if rank is not None and rank < len(grade_gradient):
            grade += grade_gradient[rank]

    return grade


def _dump_answer(data, path):
    if os.path.exists(path):
        warnings.warn('"%s" already exsits' % (path, ))
        return False
    if path.endswith('.hdf'):
        columns = ['fault_id', 'category', 'cmdb_id', 'index']
        target = []
        for fault_id in data:
            category, cmdb_id, candidates = data[fault_id]
            for candidate in candidates:
                target.append([str(fault_id), category, cmdb_id, candidate])
        target = pd.DataFrame(target, columns=columns)
        target.to_hdf(path, key='fault_id')
    else:
        # Default json
        with open(path, 'w') as obj:
            json.dump(data, obj, indent=2)
    return True


def _dump_data(data, path):
    if os.path.exists(path):
        warnings.warn('"%s" already exsits' % (path, ))
        return False
    with open(path, 'w') as obj:
        if path.endswith('.csv'):
            columns = ['fault_id', 'rank', 'category', 'cmdb_id', 'index']
            writer = csv.writer(obj)
            writer.writerow(columns)
            for fault_id in data:
                for rank, (category, cmdb_id, index) in enumerate(data[fault_id]):
                    writer.writerow([fault_id, rank, category, cmdb_id, index])
        else:
            # Default json
            json.dump(data, obj, indent=2)
    return True


def _demo(answer_path, result_path):
    print('Create sample gound truth at: "%s"' % (answer_path, ))
    ground_truth = {
        1: ('os', 'os_020', ('CPU_user_time', 'CPU_util_pct')),
        2: ('docker', 'docker_001', (None, )),  # Network error
        3: ('db', 'db_003', ('User_Commit', )),
        4: ('os', 'os_019', ('Memory_free', )),
    }
    _dump_answer(ground_truth, answer_path)

    print('Create submitted answer at: "%s"' % (result_path, ))
    submitted_answer = {
        1: [('docker', 'docker_001', None), ],
        2: [('docker', 'docker_001', None), ],  # Network error
        3: [('db', 'db_003', None), ('db', 'db_003', 'User_Commit')],
    }
    _dump_data(submitted_answer, result_path)

    print('Now, re-run with an action of "judge" to get a grade of 120')


def main():
    '''Entrance'''
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--answer', dest='answer', type=str,
                        default='answer.hdf', required=False,
                        help='File with ground truth.')
    parser.add_argument('-r', '--result', dest='result', type=str,
                        default='result.csv', required=False,
                        help='File with your answer.')
    parser.add_argument('action', choices=['judge', 'demo'],
                        help='Choose "demo" for demonstration.')
    parameters = parser.parse_args()

    if parameters.action == 'demo':
        _demo(parameters.answer, parameters.result)
    elif parameters.action == 'judge':
        print('Grade: %d' % (judge(parameters.answer, parameters.result), ))


if __name__ == '__main__':
    main()
