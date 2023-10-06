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

1. Install uwsgitop: ``docker compose run --rm web poetry add uwsgitop``
2. Install Locust: ``docker compose run --rm web poetry add locust``
3. Add locust to your docker-compose.yml locally, under services:

.. code-block:: shell

	locust:
	  image: locustio/locust
	  ports:
	    - "8089:8089"
	  volumes:
	    - ./:/src
	  command: >
	    -f /src/locustfile.py

4. Add the following to the web block, at the level of, and directly after, ``build``:

.. code-block:: shell

    deploy:
      resources:
        limits:
          cpus: "2"
          memory: "1g"

5. Add locustfile.py. There is an example file at ``locustfile.py.example`` in the root of the repo.  ``cp locustfile.py.example locustfile.py`` will copy it over as is. Change variables and/or add tests as needed.
6. Run ``docker-compose build``
7. Run ``docker-compose up``

******************
To test:
******************