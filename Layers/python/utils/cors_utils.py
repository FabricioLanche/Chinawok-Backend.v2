def get_cors_headers():
	"""Retorna headers CORS estándar para todas las respuestas"""
	return {
		'Content-Type': 'application/json',
		'Access-Control-Allow-Origin': '*',
		'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
		'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
	}
