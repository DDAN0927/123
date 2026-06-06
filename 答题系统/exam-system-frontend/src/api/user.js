import request from '../utils/request'

export function login(data) {
  return request.post('/user/login', data)
}

export function register(data) {
  return request.post('/user/register', data)
}

export function getUserList(params) {
  return request.get('/user/list', { params })
}

export function addUser(data) {
  return request.post('/user/add', data)
}

export function resetPassword(data) {
  return request.put('/user/reset-password', data)
}

export function deleteUser(id) {
  return request.delete(`/user/${id}`)
}
