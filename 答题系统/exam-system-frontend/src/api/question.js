import request from '../utils/request'

export function getQuestionList(params) {
  return request.get('/question/list', { params })
}

export function getQuestionById(id) {
  return request.get(`/question/${id}`)
}

export function addQuestion(data) {
  return request.post('/question', data)
}

export function updateQuestion(data) {
  return request.put('/question', data)
}

export function deleteQuestion(id) {
  return request.delete(`/question/${id}`)
}

export function getRandomPaper(params) {
  return request.get('/question/random', { params })
}
