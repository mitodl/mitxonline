=======================================
Setting up uWsgi tuning for MITx Online
=======================================

This setup satisfies the testing to help with tuning as mentioned in this `Discusssion Post <https://github.com/mitodl/hq/discussions/393>`_

Largely borrowed from work on OCW studio:

| `Adding uWSGI stats <https://github.com/mitodl/ocw-studio/pull/1898/>`_
| `Tuning the App <https://github.com/mitodl/ocw-studio/pull/1886/>`_


******************
To set up locally:
******************

Set up uwsgitop
---------------
1. Install uwsgitop: ``docker compose run --rm web poetry add uwsgitop``
2. Set UWSGI_RELOAD_ON_RSS in your .env to a high value (e.g. 500)
3. Set UWSGI_MAX_REQUESTS in your .env to a high value (e.g. 10000)
4. ``docker compose build``
5. ``docker compose up``
6. In a new terminal window/tab, ``docker compose exec web uwsgitop /tmp/uwsgi-stats.sock``
7. You should see your application's memory usage without usage. Ready to go.


Set up Locust
-------------
1. Install Locust: ``docker compose run --rm web poetry add locust``
2. Add locust to your docker-compose.yml locally, under services:

.. code-block:: shell

	locust:
	  image: locustio/locust
	  ports:
	    - "8089:8089"
	  volumes:
	    - ./:/src
	  command: >
	    -f /src/locustfile.py

3. Add the following to the web block, at the level of, and directly after, ``build``:

.. code-block:: shell

    deploy:
      resources:
        limits:
          cpus: "2"
          memory: "1g"

4. Add locustfile.py. There is an example file at ``locustfile.py.example`` in the root of the repo.  ``cp locustfile.py.example locustfile.py`` will copy it over as is. Change variables and/or add tests as needed.

Put it all together
-------------------

1. Run ``docker-compose build``
2. Run ``docker-compose up``
3. You can use locust from ``http://0.0.0.0:8089/`` in a browser
4. You can use uwsgitop in a terminal with ``docker compose exec web uwsgitop /tmp/uwsgi-stats.sock``

******************
To test:
******************

Coming soon!
