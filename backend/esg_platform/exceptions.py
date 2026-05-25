from rest_framework.views import exception_handler

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        if isinstance(response.data, dict):
            # If both 'error' and 'detail' are already present, do nothing
            if 'error' in response.data and 'detail' in response.data:
                return response
            
            # Extract detail
            detail = response.data.get('detail')
            if not detail:
                # If there are serializer validation errors, format the dictionary
                # of list of errors as a human readable string.
                err_items = []
                for k, v in response.data.items():
                    if isinstance(v, list):
                        v_str = ", ".join([str(x) for x in v])
                    else:
                        v_str = str(v)
                    err_items.append(f"{k}: {v_str}")
                detail = "; ".join(err_items)
            
            error_msg = exc.__class__.__name__
            if hasattr(exc, 'default_code'):
                error_msg = exc.default_code
            
            response.data = {
                'error': str(error_msg),
                'detail': str(detail)
            }
        elif isinstance(response.data, list):
            response.data = {
                'error': 'ValidationError',
                'detail': ", ".join([str(x) for x in response.data])
            }
    return response
