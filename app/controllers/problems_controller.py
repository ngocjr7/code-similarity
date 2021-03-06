from flask import Flask, render_template, url_for, request, redirect, \
    session, jsonify, send_file, Blueprint, stream_with_context, Response
from scoss import Scoss
from models.models import *
from zipfile import ZipFile
from config import URL
from werkzeug.utils import secure_filename
from controllers.similarity_checker import do_job
from controllers.task_queue import tq
from models.models import Status

import json
import time
import os
import shutil
import requests
import config

problems_controller = Blueprint('problems_controller', __name__)


@problems_controller.route('/api/contests/<contest_id>/problems/add', methods=['POST'])
def add_problem(contest_id):
    try:
        if len(Counter.objects) == 0:
            problem_id = 0
            Counter(name='count', count_user=0,
                    count_problem=0, count_contest=0).save()
        else:
            problem_id = Counter.objects.get(name='count').count_problem + 1
            Counter.objects(name='count').update(count_problem=problem_id)
            problem_id += 1
        problem_id = str(problem_id)
        problem_name = request.json['problem_name']
        problem_status = Status.init
        req = Contest.objects.get(contest_id=contest_id)
        contest_id = contest_id
        user_id = req.user_id
        data_problem = Problem.objects(
            user_id=user_id, contest_id=contest_id, problem_name=problem_name)
        if len(data_problem) > 0:
            return jsonify({'error': "The problem name may already exist"}), 400
        Problem(problem_id=problem_id, problem_name=problem_name,
                problem_status=problem_status, contest_id=contest_id, user_id=user_id).save()
        return jsonify({'problem_id': problem_id}), 200
    except Exception as e:
        return jsonify({"error": "Exception: {}".format(e)}), 400


@problems_controller.route('/api/contests/<contest_id>/problems', methods=['GET'])
def problems(contest_id):
    try:
        data_problems = Problem.objects(contest_id=contest_id)
        metrics = Contest.objects(contest_id=contest_id).metrics
        res = []
        for data_problem in data_problems:
            temp = data_problem.to_mongo()
            del temp['_id']
            res.append(temp)
    except Exception as e:
        return jsonify({"error": "Exception: {}".format(e)}), 400
    return jsonify({'contest_id': contest_id, 'problems': res, 'metrics':metrics}), 200


@problems_controller.route('/api/problems/<problem_id>', methods=['GET'])
def get_problem(problem_id):
    try:
        data_problem = Problem.objects.get(problem_id=problem_id)
        contest_name = Contest.objects.get(
            contest_id=data_problem.contest_id).contest_name
        data_doc = {
            'problem_id': data_problem.problem_id,
            'problem_name': data_problem.problem_name,
            'problem_status': data_problem.problem_status,
            'contest_id': data_problem.contest_id,
            'contest_name': contest_name,
            'user_id': data_problem.user_id,
            'sources': data_problem.sources,
            'metrics': data_problem.metrics
        }
    except Exception as e:
        return jsonify({"error": "Exception: {}".format(e)}), 400
    return jsonify(data_doc), 200


@problems_controller.route('/api/problems/<problem_id>', methods=['DELETE'])
def delete_problem(problem_id):
    try:
        Problem.objects(problem_id=problem_id).delete()
        info = 'Delete problem_id ' + str(problem_id)
    except Exception as e:
        return jsonify({"error": "Exception: {}".format(e)}), 400
    return jsonify({'info': info})

@problems_controller.route('/api/problems/<problem_id>/status', methods=['PUT'])
def updata_status(problem_id):
    try:
        problem_status = request.json['problem_status']
        Problem.objects(problem_id=problem_id).update(
            problem_status=problem_status)
        contest_id = Problem.objects.get(problem_id=problem_id).contest_id
        requests.get(url="{}/api/contests/{}/check_status".format(config.API_URI_SR, contest_id))
    except Exception as e:
        return jsonify({"error": "Exception: {}".format(e)}), 400
    return jsonify({'problem_id': problem_id}), 200


@problems_controller.route('/api/problems/<problem_id>/status', methods=['GET'])
def get_status(problem_id):
    try:
        data_problem = Problem.objects.get(problem_id=problem_id)
        data_doc = {
            'problem_id': data_problem.problem_id,
            'problem_name': data_problem.problem_name,
            'problem_status': data_problem.problem_status
        }
    except Exception as e:
        return jsonify({"error": "Exception: {}".format(e)}), 400
    return jsonify(data_doc), 200


@problems_controller.route('/api/problems/<problem_id>/from_zip', methods=['POST'])
def add_zip(problem_id):
    """
    folder:
    ----file1.cpp
    ----file2.cpp
    ----file3.cpp
    """
    try:
        data_problem = Problem.objects.get(problem_id=problem_id)
        sources = data_problem.sources
        with ZipFile(request.files['file'], 'r') as zf:
            zfile = zf.namelist()
            for file in zfile:
                try:
                    source_str = zf.read(file).decode('utf-8')
                except:
                    source_str = zf.read(file).decode('cp437')
                if len(file.split('/')) > 1 and file.split('/')[-1] != '':
                    data_doc = {
                        "pathfile": file.split('/')[-1],
                        "lang": file.split('.')[-1],
                        'mask': '',
                        'source_str': source_str
                    }
                    sources.append(data_doc)
        Problem.objects(problem_id=problem_id).update(sources=sources)
    except Exception as e:
        return jsonify({"error": "Exception: {}".format(e)}), 400
    return jsonify({'problem_id': problem_id}), 200


@problems_controller.route('/api/problems/<problem_id>/sources/add', methods=['POST'])
def add_source(problem_id):
    try:
        data_problem = Problem.objects.get(problem_id=problem_id)
        sources = data_problem.sources
        mask = request.form['mask']
        file = request.files['files']
        data_doc = {
            "pathfile": file.filename,
            "lang": file.filename.split('.')[-1],
            'mask': mask,
            'source_str': file.read().decode('UTF-8')
        }
        sources.append(data_doc)
        Problem.objects(problem_id=problem_id).update(sources=sources)
    except Exception as e:
        return jsonify({"error": "Exception: {}".format(e)}), 400
    return jsonify({'problem_id': problem_id}), 200

@problems_controller.route('/api/problems/<problem_id>/sources/delete_all', methods=['DELETE'])
def delete_all_sources(problem_id):
    try:
        Problem.objects(problem_id=problem_id).update(sources=[])
        info = 'Delete all sources!'
    except Exception as e:
        return jsonify({"error": "Exception: {}".format(e)}), 400
    return jsonify({'info': info})

@problems_controller.route('/api/problems/<problem_id>/results', methods=['GET'])
def get_results(problem_id):
    try:
        data_problem = Problem.objects.get(problem_id=problem_id)
        problem_name = data_problem.problem_name
        similarity_list = data_problem.similarity_list
        similarity_smoss_list = data_problem.similarity_smoss_list
        metrics = data_problem.metrics
        metric_list = []
        res = {}
        moss_threshold = 0
        for metric in metrics:
            metric_list.append(metric['name'])
            if metric['name'] == 'moss_score':
                moss_threshold = metric['threshold']

        if 'moss_score' in metric_list:
            for simi_smoss in similarity_smoss_list:
                key = hash(simi_smoss['source1']) ^ hash(simi_smoss['source2'])
                if simi_smoss['scores']['moss_score'] > moss_threshold:
                    temp_list = simi_smoss
                    res[key] = temp_list
                
            if len(metric_list) > 1:
                for simi in similarity_list:
                    key = hash(simi['source1']) ^ hash(simi['source2'])
                    if key in res.keys():
                        for metric in metric_list:
                            if metric != 'moss_score':
                                res[key]['scores'][metric] = simi['scores'][metric]
            for k in list(res):
                if len(res[k]['scores']) == 1:
                    if 'moss_score' in res[k]['scores'].keys():
                        del res[k]
        else:
            for simi in similarity_list:
                key = hash(simi['source1']) ^ hash(simi['source2'])
                temp_list = simi
                res[key] = temp_list
        check_zero = 0
        for key in res:
            total = 0
            num_of_score = 0
            if len(res[key]) == 0:
                check_zero += 1
                continue
            for score in res[key]['scores']:
                total += res[key]['scores'][score]
                num_of_score += 1
            if num_of_score != 0:
                res[key]['scores']['mean'] = total/num_of_score
        if(len(res.keys()) == check_zero):
            return jsonify({'problem_id': problem_id, 'results': [], 'problem_name': problem_name}), 200
    except Exception as e:
        return jsonify({"error": "Exception: {}".format(e)}), 400
    return jsonify({'problem_id': problem_id, 'results': list(res.values()), 'problem_name': problem_name}), 200


@problems_controller.route('/api/problems/<problem_id>/results/scoss', methods=['GET'])
def get_result_scoss(problem_id):
    try:
        data_problem = Problem.objects.get(problem_id=problem_id)
        similarity_list = data_problem.similarity_list
        alignment_list = data_problem.alignment_list
    except Exception as e:
        return jsonify({"error": "Exception: {}".format(e)}), 400
    return jsonify({'problem_id': problem_id, 'similarity_list': similarity_list, "alignment_list": alignment_list}), 200


@problems_controller.route('/api/problems/<problem_id>/results/smoss', methods=['GET'])
def get_result_smoss(problem_id):
    try:
        data_problem = Problem.objects.get(problem_id=problem_id)
        similarity_smoss_list = data_problem.similarity_smoss_list
        alignment_smoss_list = data_problem.alignment_smoss_list
    except Exception as e:
        return jsonify({"error": "Exception: {}".format(e)}), 400
    return jsonify({'problem_id': problem_id, 'similarity_smoss_list': similarity_smoss_list, "alignment_smoss_list": alignment_smoss_list}), 200


@problems_controller.route('/api/problems/<problem_id>/results/scoss', methods=['PUT'])
def update_result_scoss(problem_id):
    try:
        similarity_list = request.json['similarity_list']
        alignment_list = request.json['alignment_list']
        Problem.objects(problem_id=problem_id).update(
            similarity_list=similarity_list, alignment_list=alignment_list)
    except Exception as e:
        return jsonify({"error": "Exception: {}".format(e)}), 400
    return jsonify({'problem_id': problem_id}), 200


@problems_controller.route('/api/problems/<problem_id>/results/smoss', methods=['PUT'])
def update_result_smoss(problem_id):
    try:
        similarity_smoss_list = request.json['similarity_smoss_list']
        alignment_smoss_list = request.json['alignment_smoss_list']
        Problem.objects(problem_id=problem_id).update(
            similarity_smoss_list=similarity_smoss_list, alignment_smoss_list=alignment_smoss_list)
    except Exception as e:
        return jsonify({"error": "Exception: {}".format(e)}), 400
    return jsonify({'problem_id': problem_id}), 200


@problems_controller.route('/api/problems/<problem_id>/run', methods=['POST'])
def run_source(problem_id):
    try:
        data_problem = Problem.objects.get(problem_id=problem_id)
        metrics = request.json['metrics']
        Problem.objects(problem_id=problem_id).update(metrics=metrics)
        if len(data_problem) > 0:
            if data_problem.problem_status not in [Status.running, Status.waiting]:
                doc_status = {
                    "problem_status": Status.waiting
                }
                url_status = "{}/api/problems/{}/status".format(
                    URL, str(problem_id))

                requests.put(url=url_status, json=doc_status)
                tq.enqueue(do_job, args=(problem_id, config.JOB_TIMEOUT), job_timeout=1000)
    except Exception as e:
        raise e
        return jsonify({"error": "Exception: {}".format(e)}), 400
    return jsonify({'problem_id': problem_id}), 200

@problems_controller.route('/api/problems/<problem_id>/sources', methods=['GET'])
def get_source(problem_id):
    try:
        source1 = request.args.get('source1')
        source2 = request.args.get('source2')
        sources = []
        for source in [source1, source2]:
            data_source = Problem.objects(problem_id=problem_id).fields(sources={'$elemMatch': {'mask': source}})
            if len(data_source[0]['sources']) == 0:
                data_source = Problem.objects.filter(problem_id=problem_id).fields(sources={'$elemMatch': {'pathfile': source}})
            temp = {
                'pathfile': data_source[0]['sources'][0]['pathfile'],
                'lang': data_source[0]['sources'][0]['lang'],
                'mask': data_source[0]['sources'][0]['mask'],
                'source_str': data_source[0]['sources'][0]['source_str'],
            }
            sources.append(temp)

    except Exception as e:
        return jsonify({"error": "Exception: {}".format(e)}), 400
    return jsonify({'problem_id': problem_id, 'sources': sources}), 200

@problems_controller.route('/api/problems/<problem_id>/reset', methods=['PUT'])
def reset(problem_id):
    try:
        Problem.objects(problem_id=problem_id).update(problem_status=1, metrics=[],similarity_list=[],\
            similarity_smoss_list=[], alignment_list=[], alignment_smoss_list=[])
        contest_id = Problem.objects.get(problem_id=problem_id).contest_id
        requests.get(url="{}/api/contests/{}/check_status".format(config.API_URI_SR, contest_id))
        info = 'Reset all!'
    except Exception as e:
        return jsonify({"error": "Exception: {}".format(e)}), 400
    return jsonify({'info': info}), 200

@problems_controller.route('/problems/<problem_id>/status')
def status(problem_id):
    def check_status(problem_id):
        data_problem = Problem.objects.get(problem_id=problem_id)
        yield 'data: {}\n\n'.format(data_problem.problem_status)

    return Response(check_status(problem_id), mimetype="text/event-stream")

