import axios from 'axios';

const api = axios.create({
  baseURL: 'https://dev.rtk-smart-warehouse.ru/api/v1',
  headers: {
    "Content-Type": "application/json",
    timeout: 1000,
  },
});

api.interceptors.request.use(config => {
	const token = localStorage.getItem('token')
	if (token) {
		config.headers.Authorization = `Bearer ${token}`
	}
	return config
})

export default api;