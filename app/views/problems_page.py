import os
import sys
from werkzeug.utils import secure_filename
from flask import Flask, render_template, url_for, request, redirect, session, jsonify, Blueprint
from scoss import smoss
import requests
from sctokenizer import Source
from scoss import Scoss
from scoss.metrics import all_metrics
from models.models import db
from werkzeug.security import generate_password_hash, check_password_hash
from jinja2 import Environment
from config import URL

problems = Blueprint('problems_page', __name__)



def cal_scoss(contest_name, problem_name, sources, metrics):
	programs = []
	similarity_matrix = []
	aligment_matrix = []
	for source in sources:
		lang = source['file'].split('.')[-1]
		check = False
		for program in programs:
			if program.get_lang() == lang:
				check = True
				if source['mask'] == '':
					program.add_file(source['file'])
				else:
					program.add_file(source['file'], mask=source['mask'])
		if not check:
			sc = Scoss(lang=lang)
			for metric in all_metrics:
				for met in metrics:
					if metric.get_name() == met['name']:
						sc.add_metric(met['name'], met['threshold'])
						print(metric)
			if source['mask'] == '':
				sc.add_file(source['file'])
			else:
				sc.add_file(source['file'], mask=source['mask'])
			programs.append(sc)
	for program in programs: 
		for matrix in program.get_matches():
			similarity_matrix.append(matrix)
		for matrix in program.get_aligment_matrix():
			aligment_matrix.append(matrix)
	doc_matrix = {
		'contest_name': contest_name,
		'problem_name': problem_name,
		'similarity_matrix': similarity_matrix,
		'aligment_matrix': aligment_matrix
	} 
	url = URL + '/api/update_matrix'
	requests.put(url=url, json=doc_matrix)

def cal_smoss(contest_name, problem_name, sources, metrics):
	programs = []
	similarity_matrix = []
	aligment_matrix = []
	for source in sources:
		lang = source['file'].split('.')[-1]
		if str(lang) == 'cpp':
			lang = 'cc'
		check = False
		for program in programs:
			if str(program.get_lang()) == lang:
				check = True
				if source['mask'] == '':
					program.add_file(source['file'])
				else:
					program.add_file(source['file'], mask=source['mask'])
		if not check:
			sm = smoss.SMoss(lang=lang)
			for met in metrics:
				if met['name'] == 'smoss_metric':
					print(metrics)
					sm.set_threshold(met['threshold'])
			if source['mask'] == '':
				sm.add_file(source['file'])
			else:
				sm.add_file(source['file'], mask=source['mask'])
			programs.append(sm)
	for program in programs: 
		program.run()
		for matrix in program.get_matches():
			print(matrix)
			similarity_matrix.append(matrix)
		for matrix in convert_matrix(program.get_matches_file()):
			aligment_matrix.append(matrix)
	doc_matrix = {
		'contest_name': contest_name,
		'problem_name': problem_name,
		'similarity_matrix_smoss': similarity_matrix,
		'aligment_matrix_smoss': aligment_matrix
	} 
	url = URL + '/api/update_matrix_smoss'
	requests.put(url=url, json=doc_matrix)

def convert_matrix(aligment_matrix):
	match_dict = {}
	for name, score_dict in aligment_matrix.items():
		for other_name, scores in score_dict.items():
			key = hash(name) ^ hash(other_name)
			match = {}
			match['source1'] = name
			match['source2'] = other_name
			match['scores'] = scores
			match_dict[key] = match
	matches_alignment = list(match_dict.values())
	return matches_alignment


@problems.route('/problem', methods=['GET', 'POST'])
def problem():
	if 'logged_in' in session:
		if session['logged_in'] == True:
			if request.method == 'GET':
				info = request.args.get('info')
				contest_name = request.args.get('contest_name')
				params = {'contest_name': contest_name}
				url = URL + '/api/problem'
				req = requests.get(url=url, params=params)
				return render_template('problem.html', contest_name=contest_name,info=info, data=req.json()['problems'])
			if request.method == 'POST':
				problem_name = request.form['problem_name']
				contest_name = request.args.get('contest_name')
				data = {'problem_name': problem_name, 'contest_name':contest_name}
				url = URL + '/api/problem'
				req = requests.post(url=url, data=data)
				if 'problem_name' in req.json().keys():
					return redirect(url_for('problem', contest_name=contest_name))
				else:
					return redirect(url_for('problem',contest_name=contest_name, info='wrong'))
	return redirect(url_for('login'))

@problems.route('/source')
def source():
	if 'logged_in' in session:
		if session['logged_in'] == True:
			if request.method == 'GET':
				problem_name = request.args.get('problem_name')
				contest_name = request.args.get('contest_name')
				params = {'problem_name': problem_name, 'contest_name':contest_name}
				url = URL + '/api/problem_name'
				req = requests.get(url=url, params=params)
				if 'problem' in req.json().keys():
					return render_template('source.html', problem_name=problem_name, contest_name=contest_name,\
						 data=req.json()['problem'][0]['sources'])
	return redirect(url_for('login'))

@problems.route('/add_file', methods=['POST'])
def add_file():
	if 'logged_in' in session:
		if session['logged_in'] == True:
			if request.method == 'POST':
				problem_name = request.args.get('problem_name')
				contest_name = request.args.get('contest_name')
				params = {'problem_name': problem_name, 'contest_name':contest_name}
				url = URL + '/api/problem_name'
				req = requests.get(url=url, params=params)
				sources = []
				metrics = []
				if 'problem' in req.json().keys():
					sources = req.json()['problem'][0]['sources']
					metrics = req.json()['problem'][0]['metrics']
				files = request.files['file']
				mask = request.form['mask']
				path = os.path.join(problems.config['UPLOAD_FOLDER'], session['username'])
				if not os.path.exists(path): 
					os.mkdir(path)
				path = os.path.join(path, contest_name)
				if not os.path.exists(path): 
					os.mkdir(path)
				path = os.path.join(path, problem_name)
				if not os.path.exists(path): 
					os.mkdir(path)
				path = os.path.join(path, files.filename)
				source_str = files.read().decode('utf-8')
				print(path)
				with open(path, 'w+') as f:
					f.write(source_str)
				check = False
				for source in sources:
					if source['file'] == path:
						check = True
						source['mask'] = mask
				if not check:
					doc_source = {
						'file': path,
						'mask': mask,
					}
					sources.append(doc_source)
				data  = {
					'contest_name': contest_name,
					'problem_name': problem_name,
					'sources': sources,
					'metrics': metrics
				}
				url = URL + '/api/problem'
				req = requests.put(url=url, json=data)
				return redirect(url_for('source', contest_name=contest_name, problem_name=problem_name))
	return redirect(url_for('login'))
@problems.route('/run', methods=['POST'])
def run():
	if 'logged_in' in session:
		if session['logged_in'] == True:
			metrics = []
			for metric in all_metrics:
				if metric.name in request.form.keys():
					metric = {
						'name': metric.name,
						'threshold': int(request.form[metric.name])/100
					}
					metrics.append(metric)
			if 'smoss_metric' in request.form.keys():
				metric = {
						'name': 'smoss_metric',
						'threshold': int(request.form['smoss_metric'])/100
					}
				metrics.append(metric)
			problem_name = request.args.get('problem_name')
			contest_name = request.args.get('contest_name')
			url = URL + '/api/problem_metric'
			doc_metric = {
				'contest_name': contest_name,
				'problem_name': problem_name,
				'metrics': metrics
			}
			req = requests.put(url=url, json=doc_metric)
			params = {'problem_name': problem_name, 'contest_name':contest_name}
			url = URL + '/api/problem_name'
			req = requests.get(url=url, params=params)
			sources = []
			metrics = []
			if 'problem' in req.json().keys():
				sources = req.json()['problem'][0]['sources']
				metrics = req.json()['problem'][0]['metrics']
			if len(metrics) > 0:
				cal_scoss(contest_name, problem_name, sources, metrics)
				cal_smoss(contest_name, problem_name, sources, metrics)
				
		return redirect(url_for('res', contest_name=contest_name, problem_name=problem_name))
@problems.route('/res')
def res():
	contest_name = request.args.get('contest_name')
	problem_name = request.args.get('problem_name')
	params = {'contest_name': contest_name, 'problem_name':problem_name}
	url = URL + '/api/get_problem'
	req = requests.get(url=url, params=params)
	data = req.json()
	heads = []
	heads.append('source1')
	heads.append('source2')
	for metric in data['metrics']:
		heads.append(metric['name'])
	if len(data['similarity_matrix']) > 0:
		links = []
		for matrix in data['similarity_matrix']:
			dic = {}
			dic['source1'] = matrix['source1']
			dic['source2'] = matrix['source2']
			dic['scores'] = {}
			for metric, score in matrix['scores'].items():			
				C = int(score)*255
				R = C
				G = 0
				B = 0
				span = '<span style="color: rgb({}, {}, {})">'.format(R,G,B) + str(format(score*100, '.2f')) +'%</span>'
				dic['scores'][metric] = span
			if len(data['similarity_matrix_smoss']) > 0:
				for data_smoss in data['similarity_matrix_smoss']:
					if data_smoss['source1'] == matrix['source1'] and data_smoss['source2'] == matrix['source2']:
						C = int(data_smoss['scores']['moss_score'])*255
						R = C
						G = 0
						B = 0
						span = '<span style="color: rgb({}, {}, {})">'.format(R,G,B) + str(format(data_smoss['scores']['moss_score']*100, '.2f')) +'%</span>'
						dic['scores']['smoss_metric'] = span
					elif data_smoss['source1'] == matrix['source2'] and data_smoss['source2'] == matrix['source1']:
						C = int(data_smoss['scores']['moss_score'])*255
						R = C
						G = 0
						B = 0
						span = '<span style="color: rgb({}, {}, {})">'.format(R,G,B) + str(format(data_smoss['scores']['moss_score']*100, '.2f')) +'%</span>'
						dic['scores']['smoss_metric'] = span
			links.append(dic)
	else:
		links = []
		for matrix in data['similarity_matrix_smoss']:
			dic = {}
			dic['source1'] = matrix['source1']
			dic['source2'] = matrix['source2']
			dic['scores'] = {}
			for metric, score in matrix['scores'].items():			
				C = int(score)*255
				R = C
				G = 0
				B = 0
				span = '<span style="color: rgb({}, {}, {})">'.format(R,G,B) + str(format(score*100, '.2f')) +'%</span>'
				dic['scores']['smoss_metric'] = span
			links.append(dic)
	if 'logged_in' in session:
		if session['logged_in'] == True:
			return render_template('result.html', contest_name=contest_name, problem_name=problem_name, heads=heads, links=links)